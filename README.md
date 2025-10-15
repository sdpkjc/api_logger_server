# API Logger Server

A minimal API proxy server that logs requests and responses to a directory.

## Usage

### Run the server

```bash
DEFAULT_PROXY_BASE_URL="https://open.bigmodel.cn/api/paas/v4" DEFAULT_LOG_DIR="./logs" uvicorn api_logger_server:app --reload --port 9527
```

### Send a request

```bash
curl -X POST http://127.0.0.1:9527/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "glm-4.5",
    "messages": [{"role":"user","content":"Hello, world!"}]
  }'
```

### Send a request with base64 encoded JSON

```python
import base64
import json

j = {"a": "b"}
base64_json = base64.urlsafe_b64encode(json.dumps(j).encode()).decode("utf-8")
# "eyJhIjogImIifQ=="
```

```bash
curl -X POST http://127.0.0.1:9527/eyJhIjogImIifQ==/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "glm-4.5",
    "messages": [{"role":"user","content":"Hello, world!"}]
  }'
```

The base64 encoded JSON will be decoded and logged.

### Switch the proxy base URL and the log directory

```python
import base64
import json

j = {"PROXY_BASE_URL": "https://api.openai.com/v1", "LOG_FILE_PATH": "./logs_openai/a.json"}
base64_json = base64.urlsafe_b64encode(json.dumps(j).encode()).decode("utf-8")
# "eyJQUk9YWV9CQVNFX1VSTCI6ICJodHRwczovL2FwaS5vcGVuYWkuY29tL3YxIiwgIkxPR19GSUxFX1BBVEgiOiAiLi9sb2dzX29wZW5haS9hLmpzb24ifQ=="
```

```bash
curl -X POST http://127.0.0.1:9527/eyJQUk9YWV9CQVNFX1VSTCI6ICJodHRwczovL2FwaS5vcGVuYWkuY29tL3YxIiwgIkxPR19GSUxFX1BBVEgiOiAiLi9sb2dzX29wZW5haS9hLmpzb24ifQ==/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "glm-4.5",
    "messages": [{"role":"user","content":"Hello, world!"}]
  }'
```
