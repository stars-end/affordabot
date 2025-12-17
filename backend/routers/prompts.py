
from fastapi import APIRouter, Depends, HTTPException

from db.postgres_client import PostgresDB
from schemas.prompt import SystemPromptUpdate

router = APIRouter()

def get_db():
    return PostgresDB()

@router.get("/prompts/{prompt_type}")
async def get_system_prompt(prompt_type: str, db: PostgresDB = Depends(get_db)):
    prompt = await db.get_system_prompt(prompt_type)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt

@router.put("/prompts/{prompt_type}")
async def update_system_prompt(prompt_type: str, data: SystemPromptUpdate, db: PostgresDB = Depends(get_db)):
    if prompt_type != data.prompt_type:
        raise HTTPException(status_code=400, detail="Prompt type in URL and body do not match")
    
    new_version = await db.update_system_prompt(
        prompt_type=data.prompt_type,
        system_prompt=data.system_prompt,
        description=data.description
    )
    
    if new_version is None:
        raise HTTPException(status_code=500, detail="Failed to update prompt")
        
    return {"prompt_type": data.prompt_type, "new_version": new_version}

@router.get("/prompts")
async def get_all_prompts(db: PostgresDB = Depends(get_db)):
    # This function needs to be implemented in the PostgresDB client
    # For now, we will just fetch the legislation_analysis prompt
    prompts = await db.get_system_prompt('legislation_analysis')
    return [prompts] if prompts else []
