import shutil
from pathlib import Path
from fintech_rl.generator.company import SyntheticCompany
from fintech_rl.generator.errors import ErrorInjector
from fintech_rl.generator.provenance import create_provenance_file
from fintech_rl.generator.documents import render_episode_files
from fintech_rl.schema import TruthFile


def generate_episode(
    episode_id: str,
    seed: int,
    output_dir: Path,
    error_types: list[str]
):
    output_dir = Path(output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    company = SyntheticCompany(seed=seed, episode_id=episode_id)
    company.generate()

    injector = ErrorInjector(company=company, seed=seed)
    injector.apply_errors(error_types)

    truth_file = TruthFile(episode_id=episode_id, issues=injector.issues)
    prov_file = create_provenance_file(episode_id=episode_id, seed=seed, changes=injector.changes)

    render_episode_files(company, truth_file, prov_file, output_dir)
    print(f"Generated {episode_id} at {output_dir}: {len(company.ledger)} ledger rows, {len(truth_file.issues)} issues")


def main():
    base_dir = Path(__file__).resolve().parent.parent / "episodes"

    # Train: 10 episodes (episodes 1-3 clean, episodes 4-8 errors, 9-10 interacting)
    train_configs = [
        ("train_ep_01", 101, []),  # Clean
        ("train_ep_02", 102, []),  # Clean
        ("train_ep_03", 103, ["E1"]),
        ("train_ep_04", 104, ["E2"]),
        ("train_ep_05", 105, ["E3"]),
        ("train_ep_06", 106, ["E4"]),
        ("train_ep_07", 107, ["E1", "E2"]),
        ("train_ep_08", 108, ["E3", "E4"]),
        ("train_ep_09", 109, ["X1"]),       # Interacting
        ("train_ep_10", 110, ["X2"]),       # Interacting
    ]

    # Dev: 10 episodes (episodes 1-3 clean, 4-7 errors, 8-10 interacting)
    dev_configs = [
        ("dev_ep_01", 201, []),  # Clean
        ("dev_ep_02", 202, []),  # Clean
        ("dev_ep_03", 203, []),  # Clean (Total clean = 5 across train/dev)
        ("dev_ep_04", 204, ["E1"]),
        ("dev_ep_05", 205, ["E2"]),
        ("dev_ep_06", 206, ["E3"]),
        ("dev_ep_07", 207, ["E4"]),
        ("dev_ep_08", 208, ["X1"]),       # Interacting
        ("dev_ep_09", 209, ["X2"]),       # Interacting
        ("dev_ep_10", 210, ["X1", "X2"]), # Interacting (Total interacting = 5 across train/dev)
    ]

    print("Generating train episodes...")
    for ep_id, seed, errs in train_configs:
        generate_episode(ep_id, seed, base_dir / "train" / ep_id, errs)

    print("Generating dev episodes...")
    for ep_id, seed, errs in dev_configs:
        generate_episode(ep_id, seed, base_dir / "dev" / ep_id, errs)

    print("Finished generating all 20 episodes.")


if __name__ == "__main__":
    main()
