# AffordaBot Chat API

**Location:** `backend/routers/chat.py`

Server-Sent Events (SSE) streaming endpoint for the PolicyAgent. Enables real-time Deep Chat UI updates with live agent reasoning, tool calls, and analysis output.

**Prefix:** `/api`

> ⚠️ **Deployment Note**: The chat router (`routers/chat.py`) is fully implemented but is **not currently mounted** in `backend/main.py`. The main application does not include this router by default. To enable it, add the following to `backend/main.py`:
> ```python
> from routers import chat
> app.include_router(chat.router)
> ```

## Import

```python
from routers.chat import ChatRequest, ChatMessage
```

## Models

### ChatRequest

Request body for the chat endpoint.

```python { .api }
class ChatRequest(BaseModel):
    message: str                        # The policy question to analyze
    jurisdiction: Optional[str] = "San Jose"   # Target jurisdiction
    session_id: Optional[str] = None   # Optional session for context continuity
```

### ChatMessage

Response message format for SSE events.

```python { .api }
class ChatMessage(BaseModel):
    type: str   # "thinking" | "tool_call" | "tool_result" | "text" | "sources" | "error"
    data: dict  # Event-specific payload
```

## Endpoints

### POST /api/chat

Stream policy analysis response via Server-Sent Events.

```python { .api }
POST /api/chat
# Body: ChatRequest
# Returns: StreamingResponse (text/event-stream)
# Headers:
#   Cache-Control: no-cache
#   Connection: keep-alive
#   X-Accel-Buffering: no
#
# Each SSE event is: "data: <json>\n\n"
# JSON shape: {"type": str, "data": dict, "task_id"?: str, "tool_name"?: str}
#
# Event types:
#   "thinking"    — agent reasoning step
#   "tool_call"   — tool being invoked (data: {tool_name, args})
#   "tool_result" — tool output (data: {result})
#   "text"        — final answer text (data: {content})
#   "sources"     — citation URLs (data: {urls})
#   "done"        — stream complete ({})
#   "error"       — error occurred (data: {message})
#
# Errors:
#   500 — PolicyAgent initialization failed
```

**Usage example (JavaScript):**

```javascript
const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        message: "How will AB-1234 affect housing costs in San Jose?",
        jurisdiction: "San Jose"
    })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value);
    for (const line of text.split('\n')) {
        if (line.startsWith('data: ')) {
            const event = JSON.parse(line.slice(6));
            console.log(event.type, event.data);
            if (event.type === 'done') break;
        }
    }
}
```

### GET /api/chat/health

Health check for the chat endpoint.

```python { .api }
GET /api/chat/health
# Returns: {"status": "healthy", "endpoint": "/api/chat"}
```
