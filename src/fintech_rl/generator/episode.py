"""One deterministic, in-memory episode construction path for CLI and environment."""

from typing import Any, Mapping, Optional, Sequence, Tuple

from fintech_rl.generator.company import SyntheticCompany
from fintech_rl.generator.errors import ErrorInjector
from fintech_rl.generator.provenance import create_provenance_file
from fintech_rl.schema import ProvenanceFile, TruthFile


def generate_episode(
    seed: int,
    episode_id: str = "generated_episode",
    error_types: Optional[Sequence[str]] = None,
    generation: Optional[Mapping[str, Any]] = None,
) -> Tuple[SyntheticCompany, TruthFile, ProvenanceFile]:
    """Generate without temporary files; ``[]`` explicitly requests a clean company.

    Reproduction depends on seed, constructor configuration, error order and generator
    version. No process-global random state or wall-clock timestamp is consulted.
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if not isinstance(episode_id, str) or not episode_id:
        raise ValueError("episode_id must be a non-empty string")
    if generation is not None and not isinstance(generation, Mapping):
        raise ValueError("generation must be a mapping")
    parameters = dict(generation or {})
    if set(parameters) - {"num_cycles", "cycle_types", "refund_probability", "clean_mode"}:
        raise ValueError("Unsupported generation configuration")
    if error_types is None:
        requested_errors = [] if parameters.get("clean_mode") else ["E1", "E2", "E3", "E4"]
    elif isinstance(error_types, (list, tuple)) and all(isinstance(item, str) for item in error_types):
        requested_errors = list(error_types)
    else:
        raise ValueError("error_types must be a list of error type strings")
    if parameters.get("clean_mode") and requested_errors:
        raise ValueError("clean_mode requires an empty error_types list")
    company = SyntheticCompany(seed=seed, episode_id=episode_id, **parameters)
    company.generate()
    injector = ErrorInjector(company, seed=seed)
    injector.apply_errors(requested_errors)
    truth = TruthFile(episode_id=episode_id, issues=injector.issues)
    provenance = create_provenance_file(
        episode_id, seed, injector.changes,
        generation_config=parameters, error_types=requested_errors,
    )
    return company, truth, provenance
