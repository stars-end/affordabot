import os
import json
import urllib.request
import urllib.error

def seed_data():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("Error: Supabase credentials not found.")
        return

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    # Seed Models
    models = [
        {'provider': 'zai', 'model_name': 'glm-4', 'priority': 1, 'enabled': True, 'use_case': 'generation'},
        {'provider': 'openrouter', 'model_name': 'anthropic/claude-3-opus', 'priority': 2, 'enabled': True, 'use_case': 'generation'},
        {'provider': 'openrouter', 'model_name': 'openai/gpt-4o', 'priority': 3, 'enabled': True, 'use_case': 'review'}
    ]

    print("Seeding models...")
    req = urllib.request.Request(
        f"{url}/rest/v1/model_configs",
        data=json.dumps(models).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    try:
        with urllib.request.urlopen(req) as response:
            print(f"Models seeded: {response.status}")
    except urllib.error.HTTPError as e:
        print(f"Error seeding models: {e.code} {e.read().decode()}")

    # Seed Prompts
    prompts = [
        {
            'prompt_type': 'generation',
            'system_prompt': 'You are an expert legislative analyst. Analyze the following bill text and identify potential impacts on the cost of living for families in the specified jurisdiction. Focus on housing, utilities, transportation, and taxes. Provide a confidence score for each impact.',
            'updated_at': 'now()',
            'updated_by': 'system'
        },
        {
            'prompt_type': 'review',
            'system_prompt': 'You are a senior policy reviewer. Review the following impact analysis for accuracy, bias, and evidence. Flag any speculative claims that lack citation. Adjust confidence scores based on the strength of the evidence provided.',
            'updated_at': 'now()',
            'updated_by': 'system'
        }
    ]

    print("Seeding prompts...")
    req = urllib.request.Request(
        f"{url}/rest/v1/system_prompts",
        data=json.dumps(prompts).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    try:
        with urllib.request.urlopen(req) as response:
            print(f"Prompts seeded: {response.status}")
    except urllib.error.HTTPError as e:
        print(f"Error seeding prompts: {e.code} {e.read().decode()}")

if __name__ == "__main__":
    seed_data()
