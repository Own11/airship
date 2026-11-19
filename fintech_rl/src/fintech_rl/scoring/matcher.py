from typing import List, Set, Tuple, Dict, Any, Optional
from fintech_rl.schema import FindingClaim, TruthIssue, Manifest
from fintech_rl.scoring.tolerances import is_amount_within_tolerance


def canonicalize_ids(ids: List[str]) -> Tuple[str, ...]:
    """Returns sorted tuple of stripped unique IDs for deterministic set comparison."""
    return tuple(sorted(set(str(i).strip() for i in ids if str(i).strip())))


def is_evidence_sufficient(claimed_evidence: List[str], acceptable_evidence_sets: List[List[str]]) -> bool:
    """Checks if claimed evidence is a superset of at least one acceptable evidence set."""
    claimed_set = set(str(x).strip() for x in claimed_evidence)
    for acceptable_set in acceptable_evidence_sets:
        acc_s = set(str(x).strip() for x in acceptable_set)
        if acc_s.issubset(claimed_set):
            return True
    return False


class MatchResult:
    def __init__(self, tp_matches: List[Tuple[FindingClaim, TruthIssue]], fp_findings: List[FindingClaim], fn_issues: List[TruthIssue]):
        self.tp_matches = tp_matches
        self.fp_findings = fp_findings
        self.fn_issues = fn_issues

    @property
    def tp(self) -> int:
        return len(self.tp_matches)

    @property
    def fp(self) -> int:
        return len(self.fp_findings)

    @property
    def fn(self) -> int:
        return len(self.fn_issues)


def match_findings_to_truth(
    findings: List[FindingClaim],
    truth_issues: List[TruthIssue],
    tolerance_minor: int = 1  # 1 minor unit default tolerance for rounding differences
) -> MatchResult:
    """
    Performs deterministic, one-to-one bipartite matching between findings and truth issues.

    Rules:
    1. Finding and truth issue must match on:
       - type (exact string)
       - affected_ids (canonicalized set equality)
       - currency (exact string)
       - amount (abs(claimed - expected) <= tolerance_minor)
       - evidence_ids (must contain at least one complete acceptable_evidence_set)
    2. One-to-one matching: each truth issue can be matched at most once.
       Repeated/duplicate findings or findings with no match are FP.
    3. Deterministic tie-breaking if multiple findings match the same truth issue:
       - Closest amount match (|claimed - expected|)
       - Minimal evidence size (more concise evidence preferred)
       - Earliest submission order (index in findings list)
    """
    # Build candidate pairs
    candidates: List[Tuple[int, int, int, int, int]] = []
    # (issue_idx, amount_diff, evidence_len, finding_idx)

    for f_idx, f in enumerate(findings):
        f_affected = canonicalize_ids(f.affected_ids)
        for t_idx, t in enumerate(truth_issues):
            if f.type != t.type:
                continue
            if f.currency.upper() != t.currency.upper():
                continue
            if f_affected != canonicalize_ids(t.affected_ids):
                continue
            if not is_amount_within_tolerance(f.claimed_amount_minor, t.expected_amount_minor, tolerance_minor):
                continue
            if not is_evidence_sufficient(f.evidence_ids, t.acceptable_evidence_sets):
                continue
            
            diff = abs(f.claimed_amount_minor - t.expected_amount_minor)
            ev_len = len(f.evidence_ids)
            candidates.append((diff, ev_len, f_idx, t_idx))

    # Sort candidates by best match criteria deterministically
    candidates.sort(key=lambda x: (x[0], x[1], x[2], x[3]))

    matched_findings: Set[int] = set()
    matched_issues: Set[int] = set()
    tp_pairs: List[Tuple[FindingClaim, TruthIssue]] = []

    for diff, ev_len, f_idx, t_idx in candidates:
        if f_idx in matched_findings or t_idx in matched_issues:
            continue
        matched_findings.add(f_idx)
        matched_issues.add(t_idx)
        tp_pairs.append((findings[f_idx], truth_issues[t_idx]))

    fp_findings = [f for idx, f in enumerate(findings) if idx not in matched_findings]
    fn_issues = [t for idx, t in enumerate(truth_issues) if idx not in matched_issues]

    return MatchResult(tp_matches=tp_pairs, fp_findings=fp_findings, fn_issues=fn_issues)
