
import os
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))

openai_key = os.environ.get("OPENAI_API_KEY")
print(f"OPENAI_API_KEY present: {bool(openai_key)}")
if openai_key:
    print(f"OPENAI_API_KEY length: {len(openai_key)}")
    print(f"OPENAI_API_KEY prefix: {openai_key[:3]}...")

zai_key = os.environ.get("ZAI_API_KEY")
print(f"ZAI_API_KEY present: {bool(zai_key)}")
