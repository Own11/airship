import pytest
from fintech_rl.generator.company import SyntheticCompany
from fintech_rl.generator.errors import ErrorInjector
from fintech_rl.scoring.tolerances import convert_fx


def test_clean_company_accounting_identity():
    """Verify debit == credit across all generated transactions in clean mode."""
    company = SyntheticCompany(seed=42, episode_id="test_clean_01")
    company.generate()

    # Base ledger size
    assert len(company.ledger) >= 80
    assert len(company.invoices) >= 20

    # Test debit == credit per currency
    sums_by_currency = {}
    for r in company.ledger:
        sums_by_currency.setdefault(r.currency, {"debit": 0, "credit": 0})
        sums_by_currency[r.currency]["debit"] += r.debit_minor
        sums_by_currency[r.currency]["credit"] += r.credit_minor

    for curr, totals in sums_by_currency.items():
        assert totals["debit"] == totals["credit"], f"Currency {curr} ledger debit != credit"


def test_four_error_types_and_discrepancy():
    """Verify injection of E1, E2, E3, E4 creates reproducible and provable discrepancies."""
    # E1: Duplicate accounts
    c1 = SyntheticCompany(seed=101, episode_id="test_e1")
    c1.generate()
    inj1 = ErrorInjector(c1, seed=101)
    assert inj1.inject_e1_duplicate_accounts()
    assert len(inj1.issues) == 1
    assert inj1.issues[0].type == "duplicate_accounts"
    assert len(inj1.issues[0].acceptable_evidence_sets) >= 1

    # E2: Partial payment
    c2 = SyntheticCompany(seed=102, episode_id="test_e2")
    c2.generate()
    inj2 = ErrorInjector(c2, seed=102)
    assert inj2.inject_e2_partial_payment()
    assert len(inj2.issues) == 1
    assert inj2.issues[0].type == "partial_payment"

    # E3: Wrong FX rate or date
    c3 = SyntheticCompany(seed=103, episode_id="test_e3")
    c3.generate()
    inj3 = ErrorInjector(c3, seed=103)
    assert inj3.inject_e3_wrong_fx_or_date()
    assert len(inj3.issues) == 1
    assert inj3.issues[0].type == "wrong_fx_or_date"

    # E4: Period misclassification
    c4 = SyntheticCompany(seed=104, episode_id="test_e4")
    c4.generate()
    inj4 = ErrorInjector(c4, seed=104)
    assert inj4.inject_e4_period_misclassification()
    assert len(inj4.issues) == 1
    assert inj4.issues[0].type == "period_misclassification"


def test_interacting_scenarios():
    """Verify interacting scenarios X1 and X2."""
    # X1
    cx1 = SyntheticCompany(seed=201, episode_id="test_x1")
    cx1.generate()
    inj_x1 = ErrorInjector(cx1, seed=201)
    assert inj_x1.inject_x1_partial_fx_period_boundary()
    assert len(inj_x1.issues) == 1

    # X2
    cx2 = SyntheticCompany(seed=202, episode_id="test_x2")
    cx2.generate()
    inj_x2 = ErrorInjector(cx2, seed=202)
    assert inj_x2.inject_x2_duplicate_and_period()
    assert len(inj_x2.issues) == 2
