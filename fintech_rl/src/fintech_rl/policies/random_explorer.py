import random
from typing import Dict, Any


class RandomExplorerPolicy:
    """Randomly explores records and submits empty or random findings after several steps."""

    def __init__(self, seed: int = 42, steps_before_submit: int = 10):
        self.rng = random.Random(seed)
        self.steps_before_submit = steps_before_submit
        self.step_count = 0

    def reset(self):
        self.step_count = 0

    def act(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        self.step_count += 1
        if self.step_count >= self.steps_before_submit or observation["remaining_steps"] <= 1:
            return {"type": "submit", "findings": []}

        choices = [
            {"type": "list_records", "table": "ledger", "cursor": self.rng.randint(0, 50), "limit": 20},
            {"type": "list_records", "table": "invoices", "cursor": 0, "limit": 10},
            {"type": "list_records", "table": "payments", "cursor": 0, "limit": 10},
            {"type": "calculator", "expression": f"{self.rng.randint(10, 500)} * {self.rng.randint(2, 5)}"}
        ]
        return self.rng.choice(choices)
