import subprocess
import os

base_url = "https://api.z.ai"
paths = [
    "/reader",
    "/v1/reader",
    "/api/v1/reader",
    "/paas/v4/reader",
    "/api/paas/v4/reader",
    "/tools/reader",
    "/api/tools/reader",
    "/v4/reader"
]

print("Probing api.z.ai paths...")
api_key = os.environ.get("ZAI_API_KEY")

for path in paths:
    url = base_url + path
    cmd = [
        "/usr/bin/curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
        "-X", "POST",
        "-H", f"Authorization: Bearer {api_key}",
        url
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        code = result.stdout.strip()
        print(f"{path}: {code}")
    except Exception as e:
        print(f"{path}: Error {e}")
