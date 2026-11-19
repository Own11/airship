#!/usr/bin/env python3
"""
Airship Interactive Audit Demonstration Script.
"""
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fintech_rl.cli.commands import cmd_demo

if __name__ == "__main__":
    ep = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "train_ep_03"
    sys.exit(cmd_demo(episode_id=ep))
