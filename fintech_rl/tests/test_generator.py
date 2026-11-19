import pytest
from pathlib import Path
from fintech_rl.generator.company import SyntheticCompany
from fintech_rl.generator.errors import ErrorInjector
from fintech_rl.generator.provenance import create_provenance_file
from fintech_rl.generator.documents import render_episode_files
from fintech_rl.generator.validator import validate_episode_truth
from fintech_rl.schema import TruthFile


def test_clean_company_accounting_identity():
    """Verify debit == credit across all generated transactions in clean mode."""
    company = SyntheticCompany(seed=42, episode_id="test_clean_01")
    company.generate()

    assert len(company.ledger) >= 80
    assert len(company.invoices) >= 20

    sums_by_currency = {}
    for r in company.ledger:
        sums_by_currency.setdefault(r.currency, {"debit": 0, "credit": 0})
        sums_by_currency[r.currency]["debit"] += r.debit_minor
        sums_by_currency[r.currency]["credit"] += r.credit_minor

    for curr, totals in sums_by_currency.items():
        assert totals["debit"] == totals["credit"], f"Currency {curr} ledger debit != credit"


def test_four_error_types_and_discrepancy(tmp_path):
    """Verify injection of E1, E2, E3, E4 and auto-validation of truth."""
    for idx, err_type in enumerate(["E1", "E2", "E3", "E4"]):
        ep_dir = tmp_path / f"ep_{err_type}"
        c = SyntheticCompany(seed=300 + idx, episode_id=f"ep_{err_type}")
        c.generate()
        inj = ErrorInjector(c, seed=300 + idx)
        inj.apply_errors([err_type])
        truth = TruthFile(episode_id=f"ep_{err_type}", issues=inj.issues)
        prov = create_provenance_file(f"ep_{err_type}", 300 + idx, inj.changes)
        render_episode_files(c, truth, prov, ep_dir)

        # Run validator on generated files
        errs = validate_episode_truth(ep_dir)
        assert len(errs) == 0, f"Validator failed for {err_type}: {errs}"


def test_interacting_scenarios_validation(tmp_path):
    """Verify interacting scenarios X1 and X2 pass auto-validation."""
    for idx, scenario in enumerate(["X1", "X2"]):
        ep_dir = tmp_path / f"ep_{scenario}"
        c = SyntheticCompany(seed=400 + idx, episode_id=f"ep_{scenario}")
        c.generate()
        inj = ErrorInjector(c, seed=400 + idx)
        inj.apply_errors([scenario])
        truth = TruthFile(episode_id=f"ep_{scenario}", issues=inj.issues)
        prov = create_provenance_file(f"ep_{scenario}", 400 + idx, inj.changes)
        render_episode_files(c, truth, prov, ep_dir)

        errs = validate_episode_truth(ep_dir)
        assert len(errs) == 0, f"Validator failed for {scenario}: {errs}"


def test_all_20_episodes_validated():
    """Validates all 10 train and 10 dev episodes in episodes directory."""
    base_dir = Path(__file__).resolve().parent.parent / "episodes"
    all_eps = list((base_dir / "train").glob("train_ep_*")) + list((base_dir / "dev").glob("dev_ep_*"))
    assert len(all_eps) == 20, f"Expected 20 episodes, found {len(all_eps)}"

    for ep in all_eps:
        errs = validate_episode_truth(ep)
        assert len(errs) == 0, f"Episode {ep.name} has validation errors: {errs}"
