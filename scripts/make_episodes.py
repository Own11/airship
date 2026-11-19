#!/usr/bin/env python3
"""
Airship Episode Synthesizer.
Generates 10 train and 10 dev episodes with deterministic seeds.
"""
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fintech_rl.cli.commands import cmd_generate
from fintech_rl.generator.company import SyntheticCompany
from fintech_rl.generator.errors import ErrorInjector
from fintech_rl.generator.provenance import create_provenance_file
from fintech_rl.generator.documents import render_episode_files
from fintech_rl.schema import TruthFile


def generate_episode(episode_id: str, seed: int, output_dir: Path, error_types: list[str]):
    output_dir = Path(output_dir)
    if output_dir.exists():
        import shutil
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    company = SyntheticCompany(seed=seed, episode_id=episode_id)
    company.generate()

    injector = ErrorInjector(company=company, seed=seed)
    injector.apply_errors(error_types)

    truth_file = TruthFile(episode_id=episode_id, issues=injector.issues)
    prov_file = create_provenance_file(episode_id=episode_id, seed=seed, changes=injector.changes)

    render_episode_files(company, truth_file, prov_file, output_dir)
    return company, truth_file


def main():
    return cmd_generate()


if __name__ == "__main__":
    sys.exit(main())
