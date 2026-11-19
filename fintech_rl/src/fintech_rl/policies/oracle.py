from typing import Dict, Any, List
from pathlib import Path
import json


class OraclePolicy:
    """
    Oracle policy: only used by the evaluator.
    Reads truth.json directly from disk to submit the exact ground truth with minimal required evidence.
    Achieves maximum possible reward.
    """

    def __init__(self, episode_dir: Path):
        self.episode_dir = Path(episode_dir)
        self.has_submitted = False

    def reset(self):
        self.has_submitted = False

    def act(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        truth_path = self.episode_dir / "truth.json"
        with open(truth_path, "r", encoding="utf-8") as f:
            truth_data = json.load(f)

        findings = []
        for issue in truth_data.get("issues", []):
            findings.append({
                "type": issue["type"],
                "affected_ids": issue["affected_ids"],
                "claimed_amount_minor": issue["expected_amount_minor"],
                "currency": issue["currency"],
                "evidence_ids": issue["acceptable_evidence_sets"][0],
                "explanation": f"Discrepancy identified for {issue['affected_ids'][0]}"
            })

        return {"type": "submit", "findings": findings}
