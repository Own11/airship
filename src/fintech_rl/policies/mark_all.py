from typing import Dict, Any, List


class MarkAllPolicy:
    """
    Adversarial policy: 'Mark All'.
    Fetches some records and generates accusations for every entity and row across all 4 error types
    to game recall. Incurring massive FP penalties.
    """

    def __init__(self):
        self.step = 0

    def reset(self):
        self.step = 0

    def act(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        self.step += 1
        if self.step == 1:
            return {"type": "list_records", "table": "ledger", "cursor": 0, "limit": 20}

        # Submit huge batch of wild accusations
        records = (observation.get("action_result") or {}).get("records", [])
        findings = []
        for r in records:
            r_id = r["row_id"]
            for err_type in ["duplicate_accounts", "partial_payment", "wrong_fx_or_date", "period_misclassification"]:
                findings.append({
                    "type": err_type,
                    "affected_ids": [r_id],
                    "claimed_amount_minor": 10000,
                    "currency": r.get("currency", "USD"),
                    "evidence_ids": [r_id],
                    "explanation": "Mass attack accusation"
                })

        return {"type": "submit", "findings": findings}
