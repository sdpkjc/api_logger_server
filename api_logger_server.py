import os
import time
import json
import asyncio
from datetime import datetime
from uuid import uuid4
from typing import Dict, Optional

import httpx
from fastapi import FastAPI, Request, Header, Response
from fastapi.responses import JSONResponse, StreamingResponse

BASE_URL = os.getenv("PROXY_BASE_URL", "https://api.openai.com")
LOG_DIR = os.getenv("LOG_DIR", "./logs")
os.makedirs(LOG_DIR, exist_ok=True)

app = FastAPI(title="Minimal Proxy")


def clean_headers(headers: httpx.Headers) -> Dict[str, str]:
    return {
        k: v for k, v in headers.items()
        if k.lower() not in {
            "content-length", "connection", "transfer-encoding", "content-encoding"
        }
    }

async def log_interaction(**kw):
    ts = datetime.utcnow().isoformat(timespec="seconds")
    req_id = kw.get("request_id", str(uuid4()))
    filename = f"{ts.replace(':', '-')}_{req_id}.json"
    path = os.path.join(LOG_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(kw, f, ensure_ascii=False, indent=2)

@app.get("/health")
async def health():
    return {"ok": True}

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request, x_forwarded_for: Optional[str] = Header(None)):
    url = f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}"
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
                
                chunks = []
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
                            if lines:
                                chunks.append("".join(lines))
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
                            request_id=req_id,
                            ts=datetime.utcnow().isoformat(),
                            path=path,
                            ip=ip,
                            status_code=upstream.status_code,
                            duration_ms=int((time.perf_counter() - start) * 1000),
                            request_obj=body_json,
                            response_obj={
                                "stream": True,
                                "aggregated": "".join(chunks),
                                "stream_error": err["msg"],
                            },
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
                request_id=req_id,
                ts=datetime.utcnow().isoformat(),
                path=path,
                ip=ip,
                status_code=resp.status_code,
                duration_ms=int((time.perf_counter() - start) * 1000),
                request_obj=body_json,
                response_obj=resp_json,
            )

            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=clean_headers(resp.headers),
            )

    except httpx.HTTPError as e:
        return JSONResponse(status_code=502, content={"error": str(e)})


# pip install fastapi httpx uvicorn
# PROXY_BASE_URL="https://open.bigmodel.cn/api/paas/v4" LOG_DIR="./logs" uvicorn api_logger_server:app --reload
# OPENAI_BASE_URL="https://api.openai.com/v1" LOG_DIR="./logs" uvicorn api_logger_server:app --reload
# http://localhost:8000/
# http://localhost:8000/health
