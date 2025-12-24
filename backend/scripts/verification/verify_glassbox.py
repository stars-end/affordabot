#!/usr/bin/env python3
"""
Glass Box Verification Script for Affordabot.
Wraps 'verify_sanjose_pipeline.py' to provide a unified 'verify-glassbox' interface.

Usage:
    python verify_glassbox.py [--url <URL> (ignored for now, uses railway run)]
"""

import sys
import os
import subprocess
import argparse

def main():
    print("🔍 Affordabot Glass Box Verification")
    print("===================================")
    print("Target: San Jose RAG Pipeline (End-to-End)")
    print("Checks: Scout -> Harvester -> Scraper -> Vector DB -> Retrieval\n")

    # Delegate to the deep verification script
    # We use subprocess to ensure environment variables (like RAILWAY context) are handled by the caller or wrapped here
    
    script_path = os.path.join(os.path.dirname(__file__), 'verify_sanjose_pipeline.py')
    
    if not os.path.exists(script_path):
        print(f"❌ Error: Could not find validation script at {script_path}")
        sys.exit(1)

    # In future, if we want to hit a HTTP URL, we add logic here.
    # For now, Affordabot verification is "Pipeline Internal Integrity".
    
    # Check if we need to wrap in railway run?
    # The Makefile usually handles this, but let's be safe or just pass through.
    # We assume 'make verify-glassbox' calls this in the right context.

    cmd = [sys.executable, script_path]
    
    try:
        result = subprocess.run(cmd, check=False)
        sys.exit(result.returncode)
    except Exception as e:
        print(f"❌ Execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
