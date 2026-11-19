from typing import List, Dict, Any, Tuple
from fintech_rl.schema import FindingClaim, TruthIssue
from fintech_rl.scoring.matcher import match_findings_to_truth, MatchResult


def compute_metrics(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    """
    Computes Precision, Recall, and F1.
    Edge cases:
    - If truth is empty (FN=0) and findings empty (TP=0, FP=0) -> F1 = 1.0, P = 1.0, R = 1.0
    - If truth is empty (FN=0) but agent submitted findings (FP > 0) -> F1 = 0.0, P = 0.0, R = 1.0 (or 0.0)
    - If TP == 0 -> P = 0.0, R = 0.0, F1 = 0.0
    """
    if tp == 0 and fp == 0 and fn == 0:
        return 1.0, 1.0, 1.0
    if tp == 0 and fn == 0 and fp > 0:
        return 0.0, 1.0, 0.0
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    if precision + recall > 0:
        f1 = (2 * precision * recall) / (precision + recall)
    else:
        f1 = 0.0
    return precision, recall, f1


def compute_terminal_reward(
    f1: float,
    inspection_steps: int,
    invalid_structure: bool = False
) -> float:
    """
    Terminal reward: clip(2*F1 - 1 - 0.002*inspection_steps, -1.0, 1.0)
    If invalid_structure is True -> -1.0
    """
    if invalid_structure:
        return -1.0
    raw_reward = 2.0 * f1 - 1.0 - 0.002 * inspection_steps
    return max(-1.0, min(1.0, raw_reward))


def score_episode(
    findings: List[FindingClaim],
    truth_issues: List[TruthIssue],
    inspection_steps: int,
    tolerance_minor: int = 1
) -> Dict[str, Any]:
    match_result = match_findings_to_truth(findings, truth_issues, tolerance_minor=tolerance_minor)
    p, r, f1 = compute_metrics(match_result.tp, match_result.fp, match_result.fn)
    reward = compute_terminal_reward(f1, inspection_steps, invalid_structure=False)
    return {
        "tp": match_result.tp,
        "fp": match_result.fp,
        "fn": match_result.fn,
        "precision": p,
        "recall": r,
        "f1": f1,
        "reward": reward,
        "inspection_steps": inspection_steps,
        "match_result": match_result
    }
