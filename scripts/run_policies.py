#!/usr/bin/env python3
"""
Airship Multi-Policy Benchmark Runner.
Evaluates Oracle, Simple Reconciler, Random Explorer, and Mark All
across all 20 episodes and writes trajectories.jsonl.
"""
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fintech_rl.cli.commands import cmd_benchmark

if __name__ == "__main__":
    dataset = "all"
    for idx, arg in enumerate(sys.argv):
        if arg in ("--dataset", "-d") and idx + 1 < len(sys.argv):
            dataset = sys.argv[idx + 1]
    sys.exit(cmd_benchmark(dataset=dataset))
