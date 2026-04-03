import requests
import sys
import json
import argparse
import subprocess
import time

BASE_URL = "https://backend-dev-3d99.up.railway.app"


def test_endpoint(name, url_path, expected_status=200):
    url = f"{BASE_URL}{url_path}"
    print(f"Testing {name} ({url})...", end=" ")
    try:
        start = time.time()
        response = requests.get(url, timeout=10)
        duration = time.time() - start

        if response.status_code == expected_status:
            print(f"PASS ({duration:.2f}s)")
            try:
                data = response.json()
                return True, data
            except Exception:
                print("   Response not JSON")
                return True, response.text
        else:
            print(f"FAIL (Status: {response.status_code})")
            print(f"   Response: {response.text[:200]}")
            return False, None
    except Exception as e:
        print(f"FAIL (Exception: {e})")
        return False, None


def check_commit_freshness():
    print(f"\nChecking deployment freshness...")

    pass_build, build_data = test_endpoint("Build Identity", "/health/build")
    if not pass_build or not build_data:
        print("   -> STALE/UNKNOWN: Cannot determine runtime commit")
        return False, None, None

    runtime_sha = build_data.get("git_commit", "unknown")
    print(f"   Runtime SHA: {runtime_sha}")

    try:
        master_sha = subprocess.check_output(
            ["git", "rev-parse", "origin/master"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        print("   -> Cannot determine origin/master SHA")
        return False, runtime_sha, None

    print(f"   origin/master SHA: {master_sha}")

    if runtime_sha == master_sha:
        print("   -> FRESH: Runtime matches origin/master")
        return True, runtime_sha, master_sha
    elif runtime_sha == "unknown":
        print("   -> STALE: No commit identity injected at build time")
        return False, runtime_sha, master_sha
    else:
        print("   -> STALE: Runtime does NOT match origin/master")
        return False, runtime_sha, master_sha


def run_verification():
    print(f"Verifying Remote Deployment at {BASE_URL}\n")

    # 1. Global Health
    pass1, data1 = test_endpoint("Global Health", "/health")
    if pass1 and data1.get("status") == "healthy":
        print("   -> Status verified: healthy")
    else:
        print("   -> Unexpected health status")

    # 2. Detailed Health (checks services)
    pass2, data2 = test_endpoint("Detailed Health", "/admin/health/detailed")
    if pass2:
        db_status = data2.get("database", {}).get("status")
        print(f"   -> DB Status: {db_status}")

    # 3. Jurisdictions (checks DB query)
    pass3, data3 = test_endpoint("Jurisdictions List", "/admin/jurisdictions")
    if pass3:
        count = len(data3) if isinstance(data3, list) else 0
        print(f"   -> Found {count} jurisdictions")

    # 4. Model Configs (checks Postgres-backed admin config logic)
    pass4, data4 = test_endpoint("Model Configs", "/admin/models")
    if pass4:
        count = len(data4) if isinstance(data4, list) else 0
        print(f"   -> Found {count} model configs")

    # 5. Deployment freshness (runtime commit vs origin/master)
    pass_fresh, runtime_sha, master_sha = check_commit_freshness()

    if all([pass1, pass2, pass3, pass4]) and pass_fresh:
        print("\nALL TESTS PASSED. Deployment is operational and FRESH.")
        return 0
    elif all([pass1, pass2, pass3, pass4]):
        print("\nSERVICES OK but deployment may be STALE (runtime SHA mismatch).")
        return 1
    else:
        print("\nSOME TESTS FAILED.")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Verify remote Affordabot deployment health and commit freshness."
    )
    parser.add_argument("--base-url", default=BASE_URL, help="Runtime base URL")
    parser.add_argument(
        "--check-freshness-only",
        action="store_true",
        help="Only check deployment freshness, skip service health",
    )
    args = parser.parse_args()

    if args.base_url:
        BASE_URL = args.base_url

    if args.check_freshness_only:
        fresh, _, _ = check_commit_freshness()
        sys.exit(0 if fresh else 1)

    sys.exit(run_verification())
