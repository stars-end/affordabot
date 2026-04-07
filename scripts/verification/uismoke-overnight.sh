#!/bin/bash
set -e
 
# scripts/verification/uismoke-overnight.sh
# Run nightly smoke suite and perform automatic Beads triage
 
echo "🌙 Starting UISmoke Overnight QA..."
 
# Phase 1: Quality Gate (Deterministic substrate pack)
echo "🚧 Phase 1: Running Quality Gate (Deterministic)..."
if ! make verify-substrate-gate; then
    echo "❌ Quality Gate failed! This indicates a harness or environment regression."
    echo "📋 Running dry-run triage for forensics..."
    TARGET_DIR=substrate-gate make verify-substrate-triage ARGS="--dry-run" || true
    exit 1
fi
echo "✅ Quality Gate passed."
 
# Phase 2: Nightly Run (Substrate pack, advisory exploratory lane)
echo "🌙 Phase 2: Running substrate nightly suite..."
set +e # Don't exit on product bugs in QA mode. Capture RC manually.
make verify-substrate-nightly
NIGHTLY_RC=$?
set -e
 
# Phase 3: Triage
echo "📋 Phase 3: Running triage..."
# Always run triage regardless of nightly success/failure
TARGET_DIR=substrate-nightly make verify-substrate-triage
 
echo "✅ Overnight QA cycle complete (RC=${NIGHTLY_RC})."
exit $NIGHTLY_RC
