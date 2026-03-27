# System Prompt Management API

Implement the API routes that allow administrators to view and update the LLM system prompts used by the analysis pipeline without redeployment.

## Capabilities

### Prompt CRUD routes

- `GET /api/prompts` returns a list of all system prompts stored in the database via `get_system_prompt` queries [@test](./tests/test_list_prompts.py)
- `GET /api/prompts/{prompt_type}` returns the prompt record for the given `prompt_type`, or a 404 when the prompt_type does not exist [@test](./tests/test_get_prompt.py)
- `POST /api/prompts` accepts a `PromptUpdate` body containing `prompt_type` and `content` and calls `update_system_prompt()` on the database [@test](./tests/test_update_prompt.py)
- After a successful `POST /api/prompts`, the updated content is immediately returned in a subsequent `GET /api/prompts/{prompt_type}` call [@test](./tests/test_prompt_roundtrip.py)

## Implementation

[@generates](./src/prompts_router.py)

## API

```python { #api }
from fastapi import APIRouter
from pydantic import BaseModel
from db.postgres_client import PostgresDB

class PromptUpdate(BaseModel):
    prompt_type: str
    content: str

def create_prompts_router(db: PostgresDB) -> APIRouter:
    """Return a FastAPI APIRouter with /prompts routes attached."""
    ...
```

## Dependencies { .dependencies }

### affordabot { .dependency }

Provides `PostgresDB` with `get_system_prompt(prompt_type)` and `update_system_prompt(prompt_type, content)` methods, and the admin router pattern used throughout the affordabot API.

[@satisfied-by](affordabot)
