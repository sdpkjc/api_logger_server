# API Logger Server

A minimal API proxy server that logs requests and responses to a directory.

## Usage

### Run the server

```bash
PROXY_BASE_URL="https://open.bigmodel.cn/api/paas/v4" LOG_DIR="./logs" uvicorn api_logger_server:app --reload --port 9527
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

j = {"PROXY_BASE_URL": "https://api.openai.com/v1", "LOG_DIR": "./logs_openai"}
base64_json = base64.urlsafe_b64encode(json.dumps(j).encode()).decode("utf-8")
# "eyJQUk9YWV9CQVNFX1VSTCI6ICJodHRwczovL2FwaS5vcGVuYWkuY29tL3YxIiwgIkxPR19ESVIiOiAiLi9sb2dzX29wZW5haSJ9"
```

```bash
curl -X POST http://127.0.0.1:9527/eyJQUk9YWV9CQVNFX1VSTCI6ICJodHRwczovL2FwaS5vcGVuYWkuY29tL3YxIiwgIkxPR19ESVIiOiAiLi9sb2dzX29wZW5haSJ9/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "glm-4.5",
    "messages": [{"role":"user","content":"Hello, world!"}]
  }'
```
