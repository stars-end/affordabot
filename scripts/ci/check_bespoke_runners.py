import sys
import glob

def check_for_bespoke_runners():
    """Fail if any custom UISmoke runners are found."""
    forbidden_patterns = [
        "backend/scripts/verification/visual_story_runner.py",
        "backend/scripts/verification/unified_verify.py",
    ]
    
    found = []
    for pattern in forbidden_patterns:
        if glob.glob(pattern):
            found.append(pattern)
            
    if found:
        print(f"❌ ERROR: Bespoke UI runners detected: {found}")
        print("UISmoke is now centralized in llm-common. Use 'uismoke' CLI.")
        return False
        
    return True

if __name__ == "__main__":
    if not check_for_bespoke_runners():
        sys.exit(1)
    print("✅ No bespoke UI runners detected.")
