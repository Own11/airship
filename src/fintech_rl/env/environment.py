from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import csv
import json

from pydantic import ValidationError

from fintech_rl.schema import AccountingPolicy, FindingClaim, FindingsReport, Manifest, TruthFile
from fintech_rl.env.actions import ActionHandler
from fintech_rl.env.observation import create_initial_observation, create_step_observation
from fintech_rl.generator.episode import generate_episode
from fintech_rl.scoring.reward import score_episode


class FinancialAuditEnv:
    """Financial auditing environment with terminal-only reward and hidden evaluation.

    ``reset`` source precedence: explicit config episode_dir; seed or generation/
    error_types/episode_id configuration; last explicitly selected directory; otherwise
    deterministic generation with seed 0. A generated episode never creates a directory
    or becomes a sticky directory source. Mode persists until explicitly changed.
    """

    def __init__(self, episode_dir: Optional[Path] = None, max_steps: int = 100, mode: str = "train"):
        if isinstance(max_steps, bool) or not isinstance(max_steps, int) or not 1 <= max_steps <= 100:
            raise ValueError("max_steps must be an integer between 1 and 100")
        self._validate_mode(mode)
        self.episode_dir = Path(episode_dir) if episode_dir else None
        self._default_episode_dir = self.episode_dir
        self.max_steps = max_steps
        self.mode = mode
        self._clear_state()

    @staticmethod
    def _validate_mode(mode: str) -> None:
        if mode not in ("train", "eval"):
            raise ValueError("mode must be 'train' or 'eval'")

    def _clear_state(self) -> None:
        self.current_step = 0
        self.is_terminated = False
        self.is_truncated = False
        self.manifest_data: Dict[str, Any] = {}
        self.policy_data: Dict[str, Any] = {}
        self.action_handler: Optional[ActionHandler] = None
        self.truth_file: Optional[TruthFile] = None
        self.evaluator_reward = 0.0
        self.evaluator_metrics: Dict[str, Any] = {}
        self._ready = False

    def load_from_dir(self, episode_dir: Path) -> None:
        episode_dir = Path(episode_dir)
        with open(episode_dir / "manifest.json", encoding="utf-8") as source:
            manifest = Manifest.model_validate(json.load(source)).model_dump()
        with open(episode_dir / "policy.json", encoding="utf-8") as source:
            policy = AccountingPolicy.model_validate(json.load(source)).model_dump()

        ledger_rows = []
        with open(episode_dir / "ledger.csv", newline="", encoding="utf-8") as source:
            for row in csv.DictReader(source):
                ledger_rows.append({
                    "row_id": row["row_id"],
                    "timestamp": row["timestamp"],
                    "account": row["account"],
                    "debit_minor": int(row["debit_minor"]),
                    "credit_minor": int(row["credit_minor"]),
                    "currency": row["currency"],
                    **{key: None if row[key] in ("", "null") else row[key]
                       for key in ("entity_id", "invoice_id", "payment_id")},
                })
        with open(episode_dir / "fx.csv", newline="", encoding="utf-8") as source:
            fx_rows = list(csv.DictReader(source))
        invoices = {}
        with open(episode_dir / "invoices.jsonl", encoding="utf-8") as source:
            for line in source:
                if line.strip():
                    invoice = json.loads(line)
                    invoices[invoice["doc_id"]] = invoice
        payments = {}
        with open(episode_dir / "payments.jsonl", encoding="utf-8") as source:
            for line in source:
                if line.strip():
                    payment = json.loads(line)
                    payments[payment["doc_id"]] = payment
        truth_path = episode_dir / "truth.json"
        truth = None
        if truth_path.exists():
            with open(truth_path, encoding="utf-8") as source:
                truth = TruthFile.model_validate(json.load(source))
        handler = ActionHandler(ledger_rows, invoices, payments, fx_rows)
        self.episode_dir = episode_dir
        self._default_episode_dir = episode_dir
        self.manifest_data = manifest
        self.policy_data = policy
        self.truth_file = truth
        self.action_handler = handler

    def reset(self, seed: Optional[int] = None, config: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        self._clear_state()
        if config is None:
            config = {}
        if not isinstance(config, dict):
            raise ValueError("config must be a dictionary")
        if set(config) - {"mode", "episode_dir", "generation", "error_types", "episode_id"}:
            raise ValueError("Unsupported reset configuration")
        mode = config.get("mode", self.mode)
        self._validate_mode(mode)
        self.mode = mode
        explicit_dir = config.get("episode_dir")
        generation_requested = seed is not None or any(
            key in config for key in ("generation", "error_types", "episode_id")
        )
        if explicit_dir is not None:
            self.load_from_dir(Path(explicit_dir))
        elif self._default_episode_dir is not None and not generation_requested:
            self.load_from_dir(self._default_episode_dir)
        else:
            company, truth, _provenance = generate_episode(
                seed=0 if seed is None else seed,
                episode_id=config.get("episode_id", "generated_episode"),
                error_types=config.get("error_types"),
                generation=config.get("generation"),
            )
            self.episode_dir = None
            self.manifest_data = company.manifest.model_dump()
            self.policy_data = company.policy.model_dump()
            self.truth_file = truth
            self.action_handler = ActionHandler(
                ledger=[row.model_dump(mode="json") for row in company.ledger],
                invoices={doc.doc_id: doc.model_dump(mode="json") for doc in company.invoices},
                payments={doc.doc_id: doc.model_dump(mode="json") for doc in company.payments},
                fx_rates=[quote.model_dump(mode="json") for quote in company.fx_rates],
            )
        self._ready = True
        observation = create_initial_observation(self.manifest_data, self.policy_data, self.max_steps)
        return observation, {"episode_id": self.manifest_data.get("episode_id"), "max_steps": self.max_steps}

    def step(self, action: Dict[str, Any]) -> Tuple[Dict[str, Any], float, bool, bool, Dict[str, Any]]:
        if not self._ready:
            raise RuntimeError("Call reset() successfully before step()")
        if self.is_terminated or self.is_truncated:
            raise RuntimeError("Cannot step after termination or truncation. Call reset().")
        self.current_step += 1
        remaining_steps = max(0, self.max_steps - self.current_step)
        action_result = None
        action_error = None
        reward = 0.0
        terminated = False
        info: Dict[str, Any] = {}
        try:
            if not isinstance(action, dict) or not isinstance(action.get("type"), str):
                raise ValueError("Invalid action format: action must be a dict with a string 'type'")
            action_type = action["type"]
            if action_type == "list_records":
                action_result = self.action_handler.list_records(
                    action.get("table", "ledger"), int(action.get("cursor", 0)), int(action.get("limit", 50))
                )
            elif action_type == "get_record":
                action_result = self.action_handler.get_record(action.get("table"), action.get("id"))
            elif action_type == "get_document":
                action_result = self.action_handler.get_document(action.get("doc_id"))
            elif action_type == "calculator":
                action_result = self.action_handler.calculator(action.get("expression", ""))
            elif action_type == "submit":
                terminated = True
                self.is_terminated = True
                findings: List[FindingClaim] = []
                invalid_structure = False
                try:
                    findings = FindingsReport(
                        episode_id=self.manifest_data.get("episode_id", "unknown"),
                        findings=action.get("findings", []),
                    ).findings
                except ValidationError:
                    invalid_structure = True
                    action_error = "Invalid findings structure"
                if self.truth_file is not None:
                    score_details = score_episode(findings, self.truth_file.issues, self.current_step)
                    self.evaluator_reward = -1.0 if invalid_structure else score_details["reward"]
                    self.evaluator_metrics = {
                        key: score_details[key] for key in ("tp", "fp", "fn", "precision", "recall", "f1")
                    }
                    self.evaluator_metrics["reward"] = self.evaluator_reward
                    if self.mode == "eval":
                        info["eval_metrics"] = {}
                    else:
                        reward = self.evaluator_reward
                        info["eval_metrics"] = dict(self.evaluator_metrics)
                elif invalid_structure:
                    # Structural validity is independent of evaluator truth availability.
                    self.evaluator_reward = -1.0
                    self.evaluator_metrics = {"reward": -1.0}
                    if self.mode == "eval":
                        info["eval_metrics"] = {}
                    else:
                        reward = -1.0
                        info["eval_metrics"] = dict(self.evaluator_metrics)
                action_result = {"status": "submitted", "num_findings_submitted": len(findings)}
            else:
                action_error = "Unknown action type"
        except KeyError:
            action_error = "Record or document not found"
        except (TypeError, ValueError, ArithmeticError) as exc:
            # Handler messages are fixed, public diagnostics; never echo submitted
            # values or Pydantic validation payloads (which can include paths).
            if isinstance(exc, ValueError) and str(exc).startswith(("Unknown table", "Calculator error", "Invalid action format", "Record id", "Document id")):
                action_error = str(exc)
            else:
                action_error = "Invalid action parameters"

        truncated = self.current_step >= self.max_steps and not terminated
        if truncated:
            self.is_truncated = True
            self.evaluator_reward = -1.0
            self.evaluator_metrics = {
                "tp": 0, "fp": 0, "fn": len(self.truth_file.issues) if self.truth_file else 0,
                "precision": 0.0, "recall": 0.0, "f1": 0.0, "reward": -1.0,
            }
            if self.mode == "eval":
                info["eval_metrics"] = {}
            else:
                reward = -1.0
                info["eval_metrics"] = dict(self.evaluator_metrics)
            action_result = {}
        observation = create_step_observation(
            step=self.current_step,
            remaining_steps=remaining_steps,
            manifest_data=self.manifest_data,
            policy_data=self.policy_data,
            action_result=action_result,
            error=action_error,
        )
        return observation, reward, terminated, truncated, info
