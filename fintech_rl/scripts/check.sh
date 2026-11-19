#!/usr/bin/env bash
set -e

# Change to repository root
cd "$(dirname "$0")/.."

echo "=================================================="
echo "  Fintech RL Environment Verification Pipeline"
echo "=================================================="

# Set PYTHONHASHSEED for bit-exact reproducibility across platforms
export PYTHONHASHSEED=0

# 1. Run pytest
echo "[1/3] Running pytest..."
python3 -m pytest tests -v

# 2. Generate 10 train + 10 dev episodes
echo "[2/3] Generating train and dev episodes..."
PYTHONPATH=src python3 scripts/make_episodes.py

# 3. Run all 4 policies on all 20 episodes
echo "[3/3] Running policies on episodes..."
PYTHONPATH=src python3 scripts/run_policies.py

echo "All checks passed successfully!"
