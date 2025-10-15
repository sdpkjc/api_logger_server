import os
import time
import json
import asyncio
from datetime import datetime
from uuid import uuid4
from typing import Dict, Optional
import base64

import httpx
from fastapi import FastAPI, Request, Header, Response
from fastapi.responses import JSONResponse, StreamingResponse

DEFAULT_PROXY_BASE_URL = os.getenv("DEFAULT_PROXY_BASE_URL", "https://api.openai.com")
DEFAULT_LOG_DIR = os.getenv("DEFAULT_LOG_DIR", "./logs")

app = FastAPI(title="Logger Proxy")


def clean_headers(headers: httpx.Headers) -> Dict[str, str]:
    return {
        k: v for k, v in headers.items()
        if k.lower() not in {
            "content-length", "connection", "transfer-encoding", "content-encoding"
        }
    }

async def log_interaction(_log_file_path: str = None, **kw):
    ts = datetime.utcnow().isoformat(timespec="seconds")
    req_id = kw.get("request_id", str(uuid4()))
    if _log_file_path is None:
        filename = f"{ts.replace(':', '-')}_{req_id}.json"
        path = os.path.join(DEFAULT_LOG_DIR, filename)
    else:
        path = _log_file_path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(kw, f, ensure_ascii=False, indent=2)

@app.get("/health")
async def health():
    return {"ok": True}

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request, x_forwarded_for: Optional[str] = Header(None)):
    _proxy_base_url = DEFAULT_PROXY_BASE_URL
    _log_file_path = None
    path_split = path.split("/")
    base64_json = None
    if len(path_split) > 0:
        try:
            base64_json = json.loads(base64.urlsafe_b64decode(path_split[0]).decode("utf-8"))
            path_split = path_split[1:]
            _proxy_base_url = base64_json.get("PROXY_BASE_URL", DEFAULT_PROXY_BASE_URL)
            _log_file_path = base64_json.get("LOG_FILE_PATH", None)
        except Exception:
            pass
    path = "/".join(path_split)
    url = f"{_proxy_base_url.rstrip('/')}/{path.lstrip('/')}"
    req_id, start = str(uuid4()), time.perf_counter()
    ip = (x_forwarded_for or (request.client.host if request.client else "") or "").split(",")[0].strip()
    body = await request.body()

    try:
        body_json = json.loads(body.decode() or "{}")
    except Exception:
        body_json = None

    headers = {"Content-Type": request.headers.get("Content-Type", "application/json")}
    if auth := request.headers.get("Authorization"):
        headers["Authorization"] = auth
    if accept := request.headers.get("Accept"):
        headers["Accept"] = accept

    want_sse = "text/event-stream" in (request.headers.get("accept", "").lower()) or (
        isinstance(body_json, dict) and body_json.get("stream") is True
    )

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            if want_sse:
                client = httpx.AsyncClient(timeout=None, http2=False)

                cm = client.stream(request.method, url, headers=headers, content=body)
                upstream = await cm.__aenter__()

                parsed_chunks = []
                err = {"msg": None}

                async def gen():
                    try:
                        async for chunk in upstream.aiter_bytes():
                            yield chunk
                            text = chunk.decode("utf-8", "ignore")
                            lines = [
                                line[5:].strip()
                                for line in text.splitlines()
                                if line.startswith("data:") and line[5:].strip() not in ("", "[DONE]")
                            ]
                            for json_str in lines:
                                try:
                                    parsed_chunks.append(json.loads(json_str))
                                except json.JSONDecodeError:
                                    pass
                    except (
                        httpx.WriteError,
                        httpx.ReadError,
                        httpx.StreamError,
                        asyncio.CancelledError,
                    ) as e:
                        err["msg"] = f"StreamError: {type(e).__name__}: {e}"
                    finally:
                        await cm.__aexit__(None, None, None)
                        
                        await log_interaction(
                            _log_file_path,
                            request_id=req_id,
                            ts=datetime.utcnow().isoformat(),
                            path=path,
                            ip=ip,
                            status_code=upstream.status_code,
                            duration_ms=int((time.perf_counter() - start) * 1000),
                            request_obj=body_json,
                            response_obj={
                                "stream": True,
                                "chunks": parsed_chunks,
                                "stream_error": err["msg"],
                            },
                            base64_json=base64_json,
                        )

                return StreamingResponse(
                    gen(),
                    status_code=upstream.status_code,
                    media_type=upstream.headers.get("content-type", "text/event-stream"),
                    headers=clean_headers(upstream.headers),
                )

            resp = await client.request(request.method, url, headers=headers, content=body)
            try:
                resp_json = resp.json()
            except Exception:
                resp_json = {"non_json_body_len": len(resp.content)}

            await log_interaction(
                _log_file_path,
                request_id=req_id,
                ts=datetime.utcnow().isoformat(),
                path=path,
                ip=ip,
                status_code=resp.status_code,
                duration_ms=int((time.perf_counter() - start) * 1000),
                request_obj=body_json,
                response_obj=resp_json,
                base64_json=base64_json,
            )

            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=clean_headers(resp.headers),
            )

    except httpx.HTTPError as e:
        return JSONResponse(status_code=502, content={"error": str(e)})
