#!/usr/bin/env python3
"""Generate deterministic benchmark episodes after validating all artifacts."""
import sys
import tempfile
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fintech_rl.cli.commands import cmd_generate, stage_episode, publish_staged_episodes


def generate_episode(episode_id: str, seed: int, output_dir: Path, error_types: list[str]):
    """Compatibility helper preserving existing custom files and failed outputs."""
    output_dir = Path(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".staging-", dir=output_dir.parent) as temp_dir:
        stage_dir = Path(temp_dir) / "episode"
        company, truth = stage_episode(episode_id, seed, error_types, stage_dir)
        publish_staged_episodes([(stage_dir, output_dir)])
    return company, truth


def main():
    return cmd_generate()


if __name__ == "__main__":
    sys.exit(main())
