#!/usr/bin/env python3
"""
Verification script for Clerk Authentication Configuration.
Run this in the Railway environment to check if Auth env vars are set.
"""
import os
import sys
import logging

# Add backend to path (resolve relative to script location)
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_root = os.path.dirname(os.path.dirname(script_dir)) # backend/scripts/verification -> backend
sys.path.append(backend_root)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_auth")

def verify_auth_config():
    logger.info("🔐 Starting Clerk Auth Verification")
    
    required_vars = [
        "CLERK_JWKS_URL", 
        "CLERK_JWT_ISSUER"
    ]
    
    optional_vars = [
        "ADMIN_USER_IDS",
        "ADMIN_EMAIL_DOMAINS"
    ]

    missing = []
    for v in required_vars:
        val = os.getenv(v)
        if not val:
            missing.append(v)
        else:
            logger.info(f"✅ Found {v}: {val[:15]}...")

    if missing:
        logger.error(f"❌ Missing Critical Env Vars: {', '.join(missing)}")
        logger.error("Admin Authentication will FAIL.")
        sys.exit(1)
        
    for v in optional_vars:
        val = os.getenv(v)
        if val:
            logger.info(f"ℹ️  Configured {v}: {val}")
        else:
            logger.warning(f"⚠️  {v} not set (Admin access will rely on Role claims only)")

    # Try importing logic to ensure dependencies
    try:
        from auth.clerk import ClerkAuth
        logger.info("✅ ClerkAuth module imported successfully")
        
        # Instantiate to check initialization logic
        try:
            auth = ClerkAuth()
            logger.info(f"✅ ClerkAuth initialized (Issuer: {auth.issuer})")
        except Exception as e:
            logger.error(f"❌ ClerkAuth init failed: {e}")
            sys.exit(1)
            
    except ImportError as e:
        logger.error(f"❌ Import Failed: {e}")
        sys.exit(1)

    logger.info("🎉 Auth Configuration Verified! Admin endpoints are protectable.")

if __name__ == "__main__":
    verify_auth_config()
