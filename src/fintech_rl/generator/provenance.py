from typing import Any, List, Mapping, Sequence
from fintech_rl.schema import ProvenanceChange, ProvenanceFile


GENERATOR_VERSION = "2.0.0"


def create_provenance_file(
    episode_id: str,
    seed: int,
    changes: List[ProvenanceChange],
    *,
    generation_config: Mapping[str, Any] | None = None,
    error_types: Sequence[str] | None = None,
) -> ProvenanceFile:
    """Record reproducible inputs only in evaluator-private metadata."""
    return ProvenanceFile(
        episode_id=episode_id,
        seed=seed,
        created_at="2025-01-31T23:59:59+00:00",
        changes=changes,
        generator_version=GENERATOR_VERSION,
        generation_config=dict(generation_config or {}),
        error_types=list(error_types or []),
    )
