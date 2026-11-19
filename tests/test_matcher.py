import pytest
from fintech_rl.schema import FindingClaim, TruthIssue
from fintech_rl.scoring.matcher import match_findings_to_truth


def test_one_to_one_exact_match():
    truth = [
        TruthIssue(
            issue_id="ISSUE-01",
            type="duplicate_accounts",
            affected_ids=["ROW-1", "ROW-2"],
            expected_amount_minor=5000,
            currency="USD",
            acceptable_evidence_sets=[["DOC-1", "ROW-1"]]
        )
    ]
    findings = [
        FindingClaim(
            type="duplicate_accounts",
            affected_ids=["ROW-2", "ROW-1"],  # reversed order
            claimed_amount_minor=5000,
            currency="USD",
            evidence_ids=["DOC-1", "ROW-1", "EXTRA-01"]  # superset of acceptable evidence
        )
    ]

    res = match_findings_to_truth(findings, truth)
    assert res.tp == 1
    assert res.fp == 0
    assert res.fn == 0


def test_duplicates_and_unmatched():
    truth = [
        TruthIssue(
            issue_id="ISSUE-01",
            type="duplicate_accounts",
            affected_ids=["ROW-1", "ROW-2"],
            expected_amount_minor=5000,
            currency="USD",
            acceptable_evidence_sets=[["DOC-1"]]
        )
    ]
    # Agent submits 2 identical claims
    findings = [
        FindingClaim(
            type="duplicate_accounts",
            affected_ids=["ROW-1", "ROW-2"],
            claimed_amount_minor=5000,
            currency="USD",
            evidence_ids=["DOC-1"]
        ),
        FindingClaim(
            type="duplicate_accounts",
            affected_ids=["ROW-1", "ROW-2"],
            claimed_amount_minor=5000,
            currency="USD",
            evidence_ids=["DOC-1"]
        )
    ]

    res = match_findings_to_truth(findings, truth)
    # Exactly one matched (TP=1), duplicate marked as FP=1
    assert res.tp == 1
    assert res.fp == 1
    assert res.fn == 0


def test_insufficient_evidence():
    truth = [
        TruthIssue(
            issue_id="ISSUE-01",
            type="partial_payment",
            affected_ids=["PAY-01"],
            expected_amount_minor=3000,
            currency="USD",
            acceptable_evidence_sets=[["DOC-PAY-01", "ROW-P1"]]
        )
    ]
    findings = [
        FindingClaim(
            type="partial_payment",
            affected_ids=["PAY-01"],
            claimed_amount_minor=3000,
            currency="USD",
            evidence_ids=["DOC-PAY-01"]  # Missing ROW-P1
        )
    ]

    res = match_findings_to_truth(findings, truth)
    assert res.tp == 0
    assert res.fp == 1
    assert res.fn == 1
