"""
Airship package executable entrypoint for python -m airship.
"""
from fintech_rl.cli.main import main

if __name__ == "__main__":
    import sys
    sys.exit(main())
