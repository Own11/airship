#!/usr/bin/env python3
"""
Airship Unified CLI Runner.
"""
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fintech_rl.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
