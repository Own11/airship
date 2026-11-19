from typing import List
from fintech_rl.schema import ProvenanceChange, ProvenanceFile


def create_provenance_file(
    episode_id: str,
    seed: int,
    changes: List[ProvenanceChange]
) -> ProvenanceFile:
    return ProvenanceFile(
        episode_id=episode_id,
        seed=seed,
        created_at="2025-01-31T23:59:59+00:00",
        changes=changes
    )
