import pytest
from pathlib import Path
from fintech_rl.generator.company import SyntheticCompany
from fintech_rl.generator.errors import ErrorInjector
from fintech_rl.generator.provenance import create_provenance_file
from fintech_rl.generator.documents import render_episode_files
from fintech_rl.schema import TruthFile
from fintech_rl.env.environment import FinancialAuditEnv


@pytest.fixture
def sample_episode(tmp_path):
    ep_dir = tmp_path / "sample_ep"
    c = SyntheticCompany(seed=555, episode_id="sample_ep")
    c.generate()
    inj = ErrorInjector(c, seed=555)
    inj.inject_e1_duplicate_accounts()
    truth = TruthFile(episode_id="sample_ep", issues=inj.issues)
    prov = create_provenance_file("sample_ep", 555, inj.changes)
    render_episode_files(c, truth, prov, ep_dir)
    return ep_dir


def test_env_reset_and_no_leakage(sample_episode):
    env = FinancialAuditEnv()
    obs, info = env.reset(config={"episode_dir": sample_episode})

    # Validate observation structure
    assert "remaining_steps" in obs
    assert "task_description" in obs
    assert "manifest_summary" in obs
    assert "action_result" in obs
    assert obs["remaining_steps"] == 100

    # Ensure no leakage of truth, provenance or seed
    obs_str = str(obs)
    assert "truth" not in obs_str.lower()
    assert "provenance" not in obs_str.lower()
    assert "issue_id" not in obs_str
    assert "acceptable_evidence_sets" not in obs_str


def test_env_actions_and_limits(sample_episode):
    env = FinancialAuditEnv(max_steps=5)
    obs, _ = env.reset(config={"episode_dir": sample_episode})

    # Action 1: list_records
    obs1, r1, term1, trunc1, _ = env.step({"type": "list_records", "table": "ledger", "limit": 10})
    assert r1 == 0.0
    assert not term1
    assert not trunc1
    assert len(obs1["action_result"]["records"]) == 10

    # Action 2: calculator
    obs2, r2, term2, trunc2, _ = env.step({"type": "calculator", "expression": "1250 * 4"})
    assert obs2["action_result"]["result"] == "5000"

    # Action 3: get_record (invalid id)
    obs3, r3, term3, trunc3, _ = env.step({"type": "get_record", "table": "ledger", "id": "NON_EXISTENT"})
    assert obs3["error"] is not None
    assert "not found" in obs3["error"]

    # Step to exhaustion
    obs4, _, _, trunc4, _ = env.step({"type": "calculator", "expression": "1+1"})
    obs5, r5, term5, trunc5, _ = env.step({"type": "calculator", "expression": "2+2"})
    assert trunc5 is True
    assert r5 == -1.0  # budget exhausted without submission penalty
