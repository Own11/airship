from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import json
import csv
from fintech_rl.schema import Manifest, AccountingPolicy, TruthFile, FindingClaim, FindingsReport
from fintech_rl.env.actions import ActionHandler
from fintech_rl.env.observation import create_initial_observation, create_step_observation
from fintech_rl.scoring.reward import score_episode


class FinancialAuditEnv:
    """
    Gymnasium-compatible contract environment for AI Financial Statement Auditor.
    - reset(seed, config) -> (observation, info)
    - step(action) -> (observation, reward, terminated, truncated, info)
    - Maximum 100 steps
    - Terminal reward only, interim rewards = 0.0
    - Truth and provenance strictly hidden from observation and error messages.
    """

    def __init__(self, episode_dir: Optional[Path] = None, max_steps: int = 100):
        self.episode_dir = Path(episode_dir) if episode_dir else None
        self.max_steps = max_steps
        self.current_step = 0
        self.is_terminated = False
        self.is_truncated = False

        # In-memory storage for open files
        self.manifest_data: Dict[str, Any] = {}
        self.policy_data: Dict[str, Any] = {}
        self.action_handler: Optional[ActionHandler] = None

        # Evaluator only (kept outside observation)
        self.truth_file: Optional[TruthFile] = None

    def load_from_dir(self, episode_dir: Path):
        self.episode_dir = Path(episode_dir)
        with open(self.episode_dir / "manifest.json", "r", encoding="utf-8") as f:
            self.manifest_data = json.load(f)

        with open(self.episode_dir / "policy.json", "r", encoding="utf-8") as f:
            self.policy_data = json.load(f)

        ledger_rows = []
        with open(self.episode_dir / "ledger.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                ledger_rows.append({
                    "row_id": r["row_id"],
                    "timestamp": r["timestamp"],
                    "account": r["account"],
                    "debit_minor": int(r["debit_minor"]),
                    "credit_minor": int(r["credit_minor"]),
                    "currency": r["currency"],
                    "entity_id": r["entity_id"] or None,
                    "invoice_id": r["invoice_id"] or None,
                    "payment_id": r["payment_id"] or None
                })

        fx_rows = []
        with open(self.episode_dir / "fx.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                fx_rows.append(r)

        invoices = {}
        with open(self.episode_dir / "invoices.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    inv = json.loads(line)
                    invoices[inv["doc_id"]] = inv

        payments = {}
        with open(self.episode_dir / "payments.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    pay = json.loads(line)
                    payments[pay["doc_id"]] = pay

        self.action_handler = ActionHandler(
            ledger=ledger_rows,
            invoices=invoices,
            payments=payments,
            fx_rates=fx_rows
        )

        # Truth is loaded for terminal evaluation ONLY
        truth_path = self.episode_dir / "truth.json"
        if truth_path.exists():
            with open(truth_path, "r", encoding="utf-8") as f:
                self.truth_file = TruthFile.model_validate(json.load(f))
        else:
            self.truth_file = None

    def reset(self, seed: Optional[int] = None, config: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        self.current_step = 0
        self.is_terminated = False
        self.is_truncated = False

        if config and "episode_dir" in config:
            self.load_from_dir(Path(config["episode_dir"]))
        elif self.episode_dir:
            self.load_from_dir(self.episode_dir)
        else:
            raise ValueError("Episode directory must be provided either in config or at init")

        obs = create_initial_observation(
            manifest_data=self.manifest_data,
            policy_data=self.policy_data,
            remaining_steps=self.max_steps
        )
        info = {
            "episode_id": self.manifest_data.get("episode_id"),
            "max_steps": self.max_steps
        }
        return obs, info

    def step(self, action: Dict[str, Any]) -> Tuple[Dict[str, Any], float, bool, bool, Dict[str, Any]]:
        if self.is_terminated or self.is_truncated:
            raise RuntimeError("Cannot step in an environment that is already terminated or truncated. Call reset().")

        self.current_step += 1
        remaining_steps = max(0, self.max_steps - self.current_step)

        if not isinstance(action, dict) or "type" not in action:
            # Invalid action shape
            obs = create_step_observation(
                step=self.current_step,
                remaining_steps=remaining_steps,
                manifest_data=self.manifest_data,
                policy_data=self.policy_data,
                error="Invalid action format: action must be a dict with 'type'"
            )
            truncated = (self.current_step >= self.max_steps)
            self.is_truncated = truncated
            return obs, 0.0, False, truncated, {"error": "Invalid action format"}

        action_type = action["type"]
        action_result = None
        action_error = None
        reward = 0.0
        terminated = False
        info: Dict[str, Any] = {}

        try:
            if action_type == "list_records":
                table = action.get("table", "ledger")
                cursor = int(action.get("cursor", 0))
                limit = int(action.get("limit", 50))
                action_result = self.action_handler.list_records(table, cursor, limit)

            elif action_type == "get_record":
                table = action.get("table")
                id_val = action.get("id")
                action_result = self.action_handler.get_record(table, id_val)

            elif action_type == "get_document":
                doc_id = action.get("doc_id")
                action_result = self.action_handler.get_document(doc_id)

            elif action_type == "calculator":
                expression = action.get("expression", "")
                action_result = self.action_handler.calculator(expression)

            elif action_type == "submit":
                terminated = True
                self.is_terminated = True
                findings_raw = action.get("findings", [])
                findings: List[FindingClaim] = []
                invalid_structure = False
                
                try:
                    report = FindingsReport(
                        episode_id=self.manifest_data.get("episode_id", "unknown"),
                        findings=findings_raw
                    )
                    findings = report.findings
                except Exception as ex:
                    invalid_structure = True
                    action_error = f"Invalid findings structure: {str(ex)}"

                # Score submission
                if self.truth_file:
                    score_details = score_episode(
                        findings=findings,
                        truth_issues=self.truth_file.issues,
                        inspection_steps=self.current_step
                    )
                    if invalid_structure:
                        reward = -1.0
                    else:
                        reward = score_details["reward"]

                    info["eval_metrics"] = {
                        "tp": score_details["tp"],
                        "fp": score_details["fp"],
                        "fn": score_details["fn"],
                        "precision": score_details["precision"],
                        "recall": score_details["recall"],
                        "f1": score_details["f1"],
                        "reward": reward
                    }
                else:
                    reward = 0.0

                action_result = {
                    "status": "submitted",
                    "num_findings_submitted": len(findings)
                }

            else:
                action_error = f"Unknown action type '{action_type}'"

        except Exception as e:
            action_error = str(e)

        truncated = (self.current_step >= self.max_steps and not terminated)
        if truncated:
            self.is_truncated = True
            # Budget exhausted without submission: reward = -1.0 if not submitted, empty result
            reward = -1.0
            action_result = {}
            info["eval_metrics"] = {"tp": 0, "fp": 0, "fn": len(self.truth_file.issues) if self.truth_file else 0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "reward": -1.0}

        obs = create_step_observation(
            step=self.current_step,
            remaining_steps=remaining_steps,
            manifest_data=self.manifest_data,
            policy_data=self.policy_data,
            action_result=action_result,
            error=action_error
        )

        return obs, reward, terminated, truncated, info
