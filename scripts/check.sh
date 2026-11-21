#!/usr/bin/env bash
set -e

# Change to repository root
cd "$(dirname "$0")/.."

# Terminal Colors
CYAN="\033[38;5;45m"
GREEN="\033[38;5;48m"
PURPLE="\033[38;5;141m"
BOLD="\033[1m"
GRAY="\033[38;5;244m"
RESET="\033[0m"

echo ""
echo -e "${CYAN}${BOLD}╭──────────────────────────────────────────────────────────────╮${RESET}"
echo -e "${CYAN}${BOLD}│       AIRSHIP FINTECH RL: REPRODUCIBILITY & INTEGRITY        │${RESET}"
echo -e "${CYAN}${BOLD}╰──────────────────────────────────────────────────────────────╯${RESET}"
echo -e "${GRAY}Python 3.11+  •  Isolated Network  •  Deterministic Verification${RESET}"
echo ""

# Set PYTHONHASHSEED for bit-exact reproducibility across platforms
export PYTHONHASHSEED=0

# 1. Run pytest
echo -e "${PURPLE}${BOLD}[1/3]${RESET} ${BOLD}Running pytest test suite (unit, integration & contract tests)...${RESET}"
mkdir -p work
python3 -m pytest tests -v --basetemp=work/pytest-check
echo -e "${GREEN}✓ Pytest suite completed without errors.${RESET}"
echo ""

# 2. Generate 10 train + 10 dev episodes
echo -e "${PURPLE}${BOLD}[2/3]${RESET} ${BOLD}Synthesizing train & dev benchmark episodes...${RESET}"
PYTHONPATH=src python3 scripts/make_episodes.py
echo ""

# 3. Run all 4 policies on all 20 episodes
echo -e "${PURPLE}${BOLD}[3/3]${RESET} ${BOLD}Benchmarking 4 baseline policies on 20 episodes...${RESET}"
PYTHONPATH=src python3 scripts/run_policies.py
echo ""

echo -e "${GREEN}${BOLD}================================================================${RESET}"
echo -e "${GREEN}${BOLD}  ✓ ALL VERIFICATION CHECKS PASSED    ${RESET}"
echo -e "${GREEN}${BOLD}================================================================${RESET}"
echo ""
