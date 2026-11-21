from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class Observation(BaseModel):
    step: int
    remaining_steps: int
    task_description: str
    manifest_summary: Dict[str, Any]
    policy_summary: Dict[str, Any]
    action_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def create_initial_observation(
    manifest_data: Dict[str, Any],
    policy_data: Dict[str, Any],
    remaining_steps: int = 100
) -> Dict[str, Any]:
    """
    Creates initial observation without leaking hidden fields, paths, seeds, truth or provenance.
    """
    # Safe manifest projection
    safe_manifest = {
        "episode_id": manifest_data.get("episode_id"),
        "base_currency": manifest_data.get("base_currency"),
        "period_start": manifest_data.get("period_start"),
        "period_end": manifest_data.get("period_end"),
        "timezone": manifest_data.get("timezone"),
        "n_records": manifest_data.get("n_records"),
        "n_documents": manifest_data.get("n_documents"),
        "rounding_rules": manifest_data.get("rounding_rules")
    }

    obs = Observation(
        step=0,
        remaining_steps=remaining_steps,
        task_description="Audit financial records and documents for discrepancies (duplicates, partial payments, FX errors, period errors). Submit findings with valid evidence.",
        manifest_summary=safe_manifest,
        policy_summary={key: policy_data.get(key) for key in ("fx_rate_date_rule", "period_boundary_rule", "rounding")},
        action_result={"status": "episode_started"},
        error=None
    )
    return obs.model_dump()


def create_step_observation(
    step: int,
    remaining_steps: int,
    manifest_data: Dict[str, Any],
    policy_data: Dict[str, Any],
    action_result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None
) -> Dict[str, Any]:
    safe_manifest = {
        "episode_id": manifest_data.get("episode_id"),
        "base_currency": manifest_data.get("base_currency"),
        "period_start": manifest_data.get("period_start"),
        "period_end": manifest_data.get("period_end"),
        "timezone": manifest_data.get("timezone"),
        "n_records": manifest_data.get("n_records"),
        "n_documents": manifest_data.get("n_documents"),
        "rounding_rules": manifest_data.get("rounding_rules")
    }

    obs = Observation(
        step=step,
        remaining_steps=remaining_steps,
        task_description="Audit financial records and documents for discrepancies.",
        manifest_summary=safe_manifest,
        policy_summary={key: policy_data.get(key) for key in ("fx_rate_date_rule", "period_boundary_rule", "rounding")},
        action_result=action_result,
        error=error
    )
    return obs.model_dump()
