import pytest
from fintech_rl.schema import FindingClaim, TruthIssue
from fintech_rl.scoring.reward import score_episode, compute_terminal_reward


def test_silence_on_clean_better_than_false_accusation():
    """Silence on clean episode (F1=1) yields higher reward than false accusation (F1=0)."""
    truth = []  # Clean company
    silence_findings = []
    false_findings = [
        FindingClaim(
            type="duplicate_accounts",
            affected_ids=["ROW-1"],
            claimed_amount_minor=1000,
            currency="USD",
            evidence_ids=["DOC-1"]
        )
    ]

    res_silence = score_episode(silence_findings, truth, inspection_steps=1)
    res_false = score_episode(false_findings, truth, inspection_steps=1)

    assert res_silence["f1"] == 1.0
    assert res_false["f1"] == 0.0
    assert res_silence["reward"] > res_false["reward"]


def test_full_correct_better_than_silence_on_error():
    """On an erroneous episode, full correct report beats silence."""
    truth = [
        TruthIssue(
            issue_id="ISSUE-01",
            type="wrong_fx_or_date",
            affected_ids=["INV-01"],
            expected_amount_minor=2000,
            currency="USD",
            acceptable_evidence_sets=[["DOC-01"]]
        )
    ]
    correct_findings = [
        FindingClaim(
            type="wrong_fx_or_date",
            affected_ids=["INV-01"],
            claimed_amount_minor=2000,
            currency="USD",
            evidence_ids=["DOC-01"]
        )
    ]
    silence_findings = []

    res_correct = score_episode(correct_findings, truth, inspection_steps=1)
    res_silence = score_episode(silence_findings, truth, inspection_steps=1)

    assert res_correct["reward"] > res_silence["reward"]
    assert res_correct["f1"] == 1.0
    assert res_silence["f1"] == 0.0


def test_mark_all_attack_penalized():
    """Flooding with accusations yields very low precision and negative return."""
    truth = [
        TruthIssue(
            issue_id="ISSUE-01",
            type="duplicate_accounts",
            affected_ids=["ROW-1"],
            expected_amount_minor=1000,
            currency="USD",
            acceptable_evidence_sets=[["DOC-1"]]
        )
    ]
    # Mark-all flood: 1 match + 49 false accusations
    findings = [
        FindingClaim(
            type="duplicate_accounts",
            affected_ids=["ROW-1"],
            claimed_amount_minor=1000,
            currency="USD",
            evidence_ids=["DOC-1"]
        )
    ]
    for i in range(49):
        findings.append(FindingClaim(
            type="duplicate_accounts",
            affected_ids=[f"FAKE-{i}"],
            claimed_amount_minor=1000,
            currency="USD",
            evidence_ids=[f"DOC-FAKE-{i}"]
        ))

    res = score_episode(findings, truth, inspection_steps=10)
    assert res["tp"] == 1
    assert res["fp"] == 49
    assert res["precision"] == 0.02
    assert res["f1"] < 0.05
    assert res["reward"] < -0.8


def test_step_penalty_minor():
    """Fewer steps gives small bonus, but quality dominates."""
    r_fast = compute_terminal_reward(f1=1.0, inspection_steps=5)
    r_slow = compute_terminal_reward(f1=1.0, inspection_steps=25)
    assert r_fast > r_slow
    assert abs(r_fast - r_slow) <= 0.05  # Slight difference, not dominating F1
