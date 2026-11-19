import pytest
from fintech_rl.schema import FindingClaim, TruthIssue
from fintech_rl.scoring.matcher import match_findings_to_truth
from fintech_rl.scoring.reward import score_episode, compute_terminal_reward, compute_metrics
from fintech_rl.env.environment import FinancialAuditEnv
from fintech_rl.generator.company import SyntheticCompany
from fintech_rl.generator.errors import ErrorInjector
from fintech_rl.generator.provenance import create_provenance_file
from fintech_rl.generator.documents import render_episode_files
from fintech_rl.schema import TruthFile


@pytest.fixture
def sample_issue():
    return TruthIssue(
        issue_id="ISSUE-01",
        type="duplicate_accounts",
        affected_ids=["ROW-01", "ROW-02"],
        expected_amount_minor=5000,
        currency="USD",
        acceptable_evidence_sets=[["DOC-01", "ROW-01"]]
    )


# 1. Attack: Mark all / flood attack
def test_attack_mark_all_penalized(sample_issue):
    truth = [sample_issue]
    # Mark all flood: 1 valid claim + 50 garbage claims
    findings = [
        FindingClaim(
            type="duplicate_accounts",
            affected_ids=["ROW-01", "ROW-02"],
            claimed_amount_minor=5000,
            currency="USD",
            evidence_ids=["DOC-01", "ROW-01"]
        )
    ]
    for i in range(50):
        findings.append(FindingClaim(
            type="duplicate_accounts",
            affected_ids=[f"FAKE-{i}"],
            claimed_amount_minor=1000,
            currency="USD",
            evidence_ids=[f"DOC-{i}"]
        ))

    res = score_episode(findings, truth, inspection_steps=5)
    assert res["tp"] == 1
    assert res["fp"] == 50
    assert res["fn"] == 0
    assert res["precision"] < 0.05
    assert res["f1"] < 0.05
    assert res["reward"] < -0.8


# 2. Attack: Duplicates spam
def test_attack_duplicate_claims_yield_fp(sample_issue):
    truth = [sample_issue]
    # Submitting same finding 4 times
    claim = FindingClaim(
        type="duplicate_accounts",
        affected_ids=["ROW-01", "ROW-02"],
        claimed_amount_minor=5000,
        currency="USD",
        evidence_ids=["DOC-01", "ROW-01"]
    )
    findings = [claim, claim, claim, claim]

    res = score_episode(findings, truth, inspection_steps=2)
    assert res["tp"] == 1
    assert res["fp"] == 3
    assert res["fn"] == 0
    assert res["precision"] == 0.25
    assert res["reward"] < 0.0


# 3. Attack: Guessed affected IDs (wrong IDs)
def test_attack_guessed_wrong_affected_ids(sample_issue):
    truth = [sample_issue]
    findings = [
        FindingClaim(
            type="duplicate_accounts",
            affected_ids=["ROW-99", "ROW-100"],  # Guessed IDs
            claimed_amount_minor=5000,
            currency="USD",
            evidence_ids=["DOC-01", "ROW-01"]
        )
    ]
    res = score_episode(findings, truth, inspection_steps=1)
    assert res["tp"] == 0
    assert res["fp"] == 1
    assert res["fn"] == 1
    assert res["f1"] == 0.0
    assert res["reward"] <= -0.9


# 4. Attack: Incomplete / unconfirmed evidence
def test_attack_unconfirmed_evidence(sample_issue):
    truth = [sample_issue]
    findings = [
        FindingClaim(
            type="duplicate_accounts",
            affected_ids=["ROW-01", "ROW-02"],
            claimed_amount_minor=5000,
            currency="USD",
            evidence_ids=["DOC-01"]  # Missing ROW-01
        )
    ]
    res = score_episode(findings, truth, inspection_steps=1)
    assert res["tp"] == 0
    assert res["fp"] == 1
    assert res["fn"] == 1


# 5. Attack: Wrong currency
def test_attack_wrong_currency(sample_issue):
    truth = [sample_issue]
    findings = [
        FindingClaim(
            type="duplicate_accounts",
            affected_ids=["ROW-01", "ROW-02"],
            claimed_amount_minor=5000,
            currency="EUR",  # Truth is USD
            evidence_ids=["DOC-01", "ROW-01"]
        )
    ]
    res = score_episode(findings, truth, inspection_steps=1)
    assert res["tp"] == 0
    assert res["fp"] == 1
    assert res["fn"] == 1


# 6. Attack: Repeated submit in env
def test_attack_repeated_submit(tmp_path):
    ep_dir = tmp_path / "ep_repeat"
    c = SyntheticCompany(seed=42, episode_id="ep_repeat")
    c.generate()
    t = TruthFile(episode_id="ep_repeat", issues=[])
    p = create_provenance_file("ep_repeat", 42, [])
    render_episode_files(c, t, p, ep_dir)

    env = FinancialAuditEnv(episode_dir=ep_dir)
    env.reset()
    env.step({"type": "submit", "findings": []})
    # Attempting to submit again
    with pytest.raises(RuntimeError):
        env.step({"type": "submit", "findings": []})


# 7. Attack: Invalid structure in submit findings
def test_attack_invalid_findings_structure(tmp_path):
    ep_dir = tmp_path / "ep_inv"
    c = SyntheticCompany(seed=43, episode_id="ep_inv")
    c.generate()
    t = TruthFile(episode_id="ep_inv", issues=[])
    p = create_provenance_file("ep_inv", 43, [])
    render_episode_files(c, t, p, ep_dir)

    env = FinancialAuditEnv(episode_dir=ep_dir)
    env.reset()
    # Malformed finding missing required fields
    obs, reward, term, trunc, info = env.step({"type": "submit", "findings": [{"broken": "structure"}]})
    assert term is True
    assert reward == -1.0


# 8. Attack: Timeout exhaustion
def test_attack_timeout_exhaustion(tmp_path):
    ep_dir = tmp_path / "ep_to"
    c = SyntheticCompany(seed=44, episode_id="ep_to")
    c.generate()
    t = TruthFile(episode_id="ep_to", issues=[])
    p = create_provenance_file("ep_to", 44, [])
    render_episode_files(c, t, p, ep_dir)

    env = FinancialAuditEnv(episode_dir=ep_dir, max_steps=2)
    env.reset()
    env.step({"type": "calculator", "expression": "1+1"})
    obs, reward, term, trunc, info = env.step({"type": "calculator", "expression": "2+2"})
    assert trunc is True
    assert reward == -1.0


# 9. Clean company silence vs false accusation
def test_clean_company_silence_vs_accusation():
    truth = []  # Clean company
    res_silence = score_episode([], truth, inspection_steps=1)
    res_accusation = score_episode([
        FindingClaim(type="duplicate_accounts", affected_ids=["ROW-1"], claimed_amount_minor=100, currency="USD", evidence_ids=["DOC-1"])
    ], truth, inspection_steps=1)

    assert res_silence["f1"] == 1.0
    assert res_silence["reward"] > 0.95
    assert res_accusation["f1"] == 0.0
    assert res_accusation["reward"] == -1.0


# 10. Empty truth edge case metrics
def test_empty_truth_metrics():
    # Empty truth + empty findings -> F1=1.0, P=1.0, R=1.0
    p1, r1, f1_1 = compute_metrics(0, 0, 0)
    assert (p1, r1, f1_1) == (1.0, 1.0, 1.0)

    # Empty truth + findings submitted -> F1=0.0, P=0.0, R=0.0
    p2, r2, f2_2 = compute_metrics(0, 1, 0)
    assert (p2, r2, f2_2) == (0.0, 0.0, 0.0)


# 11. Ambiguity resolution (closest amount and minimal evidence)
def test_ambiguity_resolution_deterministic(sample_issue):
    truth = [sample_issue]  # amount 5000
    # Two valid candidates: Candidate A has amount 5000 (diff 0), Candidate B has amount 5001 (diff 1)
    cand_a = FindingClaim(
        type="duplicate_accounts",
        affected_ids=["ROW-01", "ROW-02"],
        claimed_amount_minor=5000,
        currency="USD",
        evidence_ids=["DOC-01", "ROW-01"]
    )
    cand_b = FindingClaim(
        type="duplicate_accounts",
        affected_ids=["ROW-01", "ROW-02"],
        claimed_amount_minor=5001,
        currency="USD",
        evidence_ids=["DOC-01", "ROW-01"]
    )
    # Order: [cand_b, cand_a]. Matcher should pick cand_a for TP because diff=0 < diff=1
    match_res = match_findings_to_truth([cand_b, cand_a], truth, tolerance_minor=1)
    assert match_res.tp == 1
    assert match_res.fp == 1
    assert match_res.tp_matches[0][0].claimed_amount_minor == 5000
