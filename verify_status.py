import json, os, urllib.request, subprocess

def check_beads():
    print("--- Beads Ready ---")
    try:
        res = subprocess.run(["bd", "ready"], capture_output=True, text=True)
        print(res.stdout)
        print(res.stderr)
    except Exception as e:
        print(f"Beads check failed: {e}")

def check_inbox():
    print("--- Agent Mail Inbox ---")
    url = os.environ.get("AGENT_MAIL_URL")
    token = os.environ.get("AGENT_MAIL_BEARER_TOKEN")
    project = os.environ.get("AGENT_MAIL_PROJECT_KEY")
    
    if not url or not token:
        print("Missing Agent Mail env vars")
        return

    req = urllib.request.Request(
        f"{url}/tools/call",
        data=json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "fetch_inbox",
                "arguments": {
                    "project_key": project,
                    "agent_name": "PurpleBear",
                    "limit": 5
                }
            }
        }).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
    )
    
    print(f"DEBUG: URL={url}/tools/call")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read()
            print(f"DEBUG: Status={resp.status}")
            print(f"DEBUG: Raw={raw}")
            data = json.loads(raw.decode())
            # Result is a ToolResult, need to parse inner text
            # result: { content: [{type:text, text:JSON_STRING}], ... }
            inner_text = data["result"]["content"][0]["text"]
            inbox = json.loads(inner_text)
            if not inbox:
                print("Inbox: Empty")
            else:
                for m in inbox:
                    print(f"- [{m['id']}] {m['subject']} (from {m['from']})")
    except Exception as e:
        print(f"Inbox check failed: {e}")

if __name__ == "__main__":
    check_beads()
    check_inbox()
