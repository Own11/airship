import pytest
from fintech_rl.generator.company import SyntheticCompany
from fintech_rl.generator.errors import ErrorInjector
from fintech_rl.schema import TruthFile
from fintech_rl.scoring.reward import score_episode
from fintech_rl.policies.oracle import OraclePolicy
from fintech_rl.generator.documents import render_episode_files
from fintech_rl.generator.provenance import create_provenance_file


def test_bit_exact_reproducibility(tmp_path):
    """Same seed and config generate bitwise identical ledger and truth."""
    ep_dir1 = tmp_path / "ep1"
    ep_dir2 = tmp_path / "ep2"

    c1 = SyntheticCompany(seed=777, episode_id="repro_ep")
    c1.generate()
    inj1 = ErrorInjector(c1, seed=777)
    inj1.inject_e1_duplicate_accounts()
    t1 = TruthFile(episode_id="repro_ep", issues=inj1.issues)
    p1 = create_provenance_file("repro_ep", 777, inj1.changes)
    render_episode_files(c1, t1, p1, ep_dir1)

    c2 = SyntheticCompany(seed=777, episode_id="repro_ep")
    c2.generate()
    inj2 = ErrorInjector(c2, seed=777)
    inj2.inject_e1_duplicate_accounts()
    t2 = TruthFile(episode_id="repro_ep", issues=inj2.issues)
    p2 = create_provenance_file("repro_ep", 777, inj2.changes)
    render_episode_files(c2, t2, p2, ep_dir2)

    # Compare generated files byte-for-byte
    for fname in ["manifest.json", "ledger.csv", "invoices.jsonl", "payments.jsonl", "truth.json"]:
        content1 = (ep_dir1 / fname).read_bytes()
        content2 = (ep_dir2 / fname).read_bytes()
        assert content1 == content2, f"File {fname} differed between identical seeds"
