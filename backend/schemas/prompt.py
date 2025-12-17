
from pydantic import BaseModel

class SystemPromptUpdate(BaseModel):
    prompt_type: str
    system_prompt: str
    description: str | None = None
