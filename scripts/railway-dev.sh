#!/bin/bash
# scripts/railway-dev.sh
# Wrapper for 'railway dev' in Affordabot

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
RESET='\033[0m'

echo -e "${GREEN}🚄 Starting Affordabot in Railway Dev Mode...${RESET}"

# check if railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo -e "${RED}Error: Railway CLI not found.${RESET}"
    echo "Install it: https://docs.railway.app/guides/cli"
    exit 1
fi

# Check for link (soft check or reliance on CLI prompt)
# 'railway status' might be too heavy, 'railway whom' checks auth.
# Just try 'railway dev --help' first? No, just run it.

echo -e "${YELLOW}Note: Ensure you are linked to the correct project (railway link)${RESET}"
echo -e "${YELLOW}If database services are not in the linked project, this will fail to start a local DB.${RESET}"

# Run railway dev
# We don't have special flags yet, let it interactively prompt for service mapping if needed.
# But we can try to pre-configure known services if we had the config.
railway dev
