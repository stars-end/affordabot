#!/bin/bash
set -e
 
# scripts/verification/uismoke-overnight.sh
# Run nightly smoke suite and perform automatic Beads triage
 
echo "🌙 Starting UISmoke Overnight QA..."
 
# Phase 1: Quality Gate (Deterministic only)
echo "🚧 Phase 1: Running Quality Gate (Deterministic)..."
if ! make verify-gate; then
    echo "❌ Quality Gate failed! This indicates a harness or environment regression."
    echo "📋 Running dry-run triage for forensics..."
    TARGET_DIR=gate make verify-triage ARGS="--dry-run" || true
    exit 1
fi
echo "✅ Quality Gate passed."
 
# Phase 2: Nightly Run (Full suite with LLM fallback)
echo "🌙 Phase 2: Running Nightly full suite..."
set +e # Don't exit on product bugs in QA mode
make verify-nightly
set -e
 
# Phase 3: Triage
echo "📋 Phase 3: Running triage..."
TARGET_DIR=nightly make verify-triage
 
echo "✅ Overnight QA cycle complete."
