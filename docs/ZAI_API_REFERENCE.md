# Z.AI API Reference & Quick Start

Source: https://docs.z.ai/guides/overview/quick-start
Coding Endpoint: https://api.z.ai/api/coding/paas/v4

## Getting Started

1. **Get API Key**: Access [Z.AI Open Platform](https://z.ai/model-api).
2. **Choose Model**:
   - **GLM-4.6**: Flagship model for agent-oriented applications.
   - **GLM-4.6V**: Multimodal model.
   - **CogView-4**: Image generation.
   - **CogVideoX-3**: Video generation.

## API Usage

### cURL Example
```bash
curl -X POST "https://api.z.ai/api/paas/v4/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "glm-4.6",
    "messages": [
      {"role": "system", "content": "You are a helpful AI assistant."},
      {"role": "user", "content": "Hello"}
    ]
  }'
```

### Python SDK (OpenAI Compatible)
```python
from openai import OpenAI

client = OpenAI(
    api_key="YOUR_API_KEY",
    base_url="https://api.z.ai/api/paas/v4"  # Or coding endpoint
)

response = client.chat.completions.create(
    model="glm-4.6",
    messages=[
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": "Hello"}
    ]
)
print(response.choices[0].message.content)
```
