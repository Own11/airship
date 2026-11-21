"""Financial invariants and unseen-seed coverage for generator scenarios."""
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

import pytest
from pydantic import ValidationError

from fintech_rl.generator.company import ACCOUNTS, SyntheticCompany
from fintech_rl.generator.errors import ErrorInjector
from fintech_rl.identifiers import fx_record_id
from fintech_rl.schema import ProvenanceFile, TruthIssue
from fintech_rl.scoring.tolerances import convert_fx


def balances(company):
    totals = defaultdict(int)
    for row in company.ledger:
        key = (row.timestamp, row.currency, row.invoice_id, row.payment_id, row.entity_id)
        totals[key] += row.debit_minor - row.credit_minor
        assert (row.debit_minor > 0) != (row.credit_minor > 0)
    assert all(total == 0 for total in totals.values())


def public_ids(company):
    return ({row.row_id for row in company.ledger}
            | {value for inv in company.invoices for value in (inv.invoice_id, inv.doc_id)}
            | {value for pay in company.payments for value in (pay.payment_id, pay.doc_id)}
            | {fx_record_id(rate.date, rate.source_currency, rate.target_currency)
               for rate in company.fx_rates})


def assert_valid_issues(company, injector):
    ids = public_ids(company)
    assert len({row.row_id for row in company.ledger}) == len(company.ledger)
    assert len(injector.issues) == len(injector.changes)
    for issue, change in zip(injector.issues, injector.changes):
        assert set(issue.affected_ids) <= ids
        assert issue.expected_amount_minor > 0
        for evidence in issue.acceptable_evidence_sets:
            assert 1 <= len(evidence) <= 10
            assert set(evidence) <= ids
        for field in issue.model_fields:
            assert getattr(change, field) == getattr(issue, field)
        assert change.before_state["rows"]
        assert change.after_state["rows"]
    assert company.manifest.n_records == len(company.ledger)
    assert company.manifest.n_documents == len(company.invoices) + len(company.payments)
    balances(company)


@pytest.mark.parametrize("seed", range(32))
def test_default_episode_bounds_and_balanced_clean_company(seed):
    company = SyntheticCompany(seed, "bounds")
    company.generate()
    assert 200 <= len(company.ledger) <= 2000
    assert 20 <= len(company.invoices) + len(company.payments) <= 200
    assert company.manifest.n_records == len(company.ledger)
    balances(company)
    invoices = {invoice.invoice_id: invoice for invoice in company.invoices}
    for payment in company.payments:
        for invoice_id in payment.invoice_refs:
            assert datetime.fromisoformat(payment.timestamp) >= datetime.fromisoformat(invoices[invoice_id].issued_at)


@pytest.mark.parametrize("cycles,kind,documents", [
    (20, "unpaid", 20), (100, "unpaid", 100), (100, "full", 200),
    (66, "split", 198), (50, "refund", 200),
])
def test_actual_size_bounds_at_extreme_cycle_configs(cycles, kind, documents):
    company = SyntheticCompany(811, "extreme", num_cycles=cycles, cycle_types=[kind])
    company.generate()
    assert 200 <= len(company.ledger) <= 2000
    assert company.manifest.n_documents == documents
    balances(company)


@pytest.mark.parametrize("config", [
    {"num_cycles": 19}, {"num_cycles": 101}, {"num_cycles": True},
    {"num_cycles": 51, "cycle_types": ["refund"]},
    {"num_cycles": 67, "cycle_types": ["split"]},
    {"cycle_types": []}, {"cycle_types": ["unknown"]}, {"cycle_types": "full"},
    {"cycle_types": 123}, {"cycle_types": [[]]},
    {"refund_probability": -0.1}, {"refund_probability": 1.1},
    {"refund_probability": float("nan")},
])
def test_invalid_generation_configs_fail_before_generation(config):
    with pytest.raises(ValueError):
        SyntheticCompany(1, "invalid", **config)


def test_repeated_generate_restarts_the_same_instance_and_rng():
    company = SyntheticCompany(12379, "repeat")
    company.generate()
    before = ([row.model_dump() for row in company.ledger],
              [doc.model_dump() for doc in company.invoices],
              [doc.model_dump() for doc in company.payments],
              [rate.model_dump() for rate in company.fx_rates])
    ErrorInjector(company, 14).apply_errors(["E1", "X1"])
    company.generate()
    after = ([row.model_dump() for row in company.ledger],
             [doc.model_dump() for doc in company.invoices],
             [doc.model_dump() for doc in company.payments],
             [rate.model_dump() for rate in company.fx_rates])
    assert before == after


def test_legal_returns_reconcile_cash_revenue_and_credit_notes():
    company = SyntheticCompany(932, "clean_returns", num_cycles=20, cycle_types=["refund"])
    company.generate()
    balances(company)
    notes = [inv for inv in company.invoices if inv.document_type == "credit_note"]
    assert len(notes) == 20
    invoices = {inv.invoice_id: inv for inv in company.invoices}
    for note in notes:
        original = invoices[note.related_invoice_id]
        assert original.document_type == "invoice"
        assert original.currency == note.currency
        assert 0 < note.total_minor <= original.total_minor
        refund = next(pay for pay in company.payments if pay.invoice_refs == [note.invoice_id])
        assert refund.direction == "refund"
        assert refund.amount_minor == note.total_minor
        assert refund.currency == note.currency
        family_rows = [row for row in company.ledger if row.invoice_id in (original.invoice_id, note.invoice_id)]
        cash = sum(row.debit_minor - row.credit_minor for row in family_rows if row.account == ACCOUNTS["CASH"])
        revenue = sum(row.credit_minor - row.debit_minor for row in family_rows if row.account == ACCOUNTS["REVENUE"])
        receivable = sum(row.debit_minor - row.credit_minor for row in family_rows if row.account == ACCOUNTS["AR"])
        assert cash == revenue == original.total_minor - note.total_minor
        assert receivable == 0
    injector = ErrorInjector(company, 10)
    injector.apply_errors([])
    assert injector.issues == injector.changes == []
    # Return families are never accidentally treated as malformed normal receipts.
    for method in (injector.inject_e1_duplicate_accounts, injector.inject_e2_partial_payment,
                   injector.inject_e3_wrong_fx_or_date, injector.inject_e4_period_misclassification):
        assert method() is False


@pytest.mark.parametrize("seed", [7, 83, 400, 1907, 49001])
def test_x1_links_partial_allocation_wrong_fx_and_period_boundary(seed):
    company = SyntheticCompany(seed, "x1", num_cycles=40, cycle_types=["full"])
    company.generate()
    injector = ErrorInjector(company, seed)
    injector.apply_errors(["X1"])
    assert [issue.type for issue in injector.issues] == ["partial_payment", "wrong_fx_or_date"]
    partial, fx = injector.issues
    pay = next(pay for pay in company.payments if pay.payment_id in partial.affected_ids)
    assert pay.payment_id in fx.affected_ids
    assert pay.currency != company.base_currency
    assert pay.timestamp == company.period_end
    rows = [row for row in company.ledger if row.payment_id == pay.payment_id]
    assert len(rows) == 4
    assert all(row.timestamp == company.period_end for row in rows)
    allocated = next(row.credit_minor for row in rows if row.account == ACCOUNTS["AR"])
    actual = next(row.debit_minor for row in rows if row.account == ACCOUNTS["CASH"])
    official = next(rate.rate for rate in company.fx_rates
                    if rate.date == pay.timestamp[:10] and rate.source_currency == pay.currency
                    and rate.target_currency == company.base_currency)
    assert allocated < pay.amount_minor
    assert partial.currency == pay.currency
    assert partial.expected_amount_minor == pay.amount_minor - allocated
    assert fx.currency == company.base_currency
    assert fx.expected_amount_minor == abs(actual - convert_fx(allocated, official)) > 0
    assert fx_record_id(pay.timestamp[:10], pay.currency, company.base_currency) in fx.acceptable_evidence_sets[0]
    assert all(change.before_state["scenario"] == "X1" for change in injector.changes)
    assert_valid_issues(company, injector)


@pytest.mark.parametrize("seed", [7, 83, 401, 1907, 49001])
def test_x2_duplicate_and_cutoff_share_one_invoice(seed):
    company = SyntheticCompany(seed, "x2")
    company.generate()
    injector = ErrorInjector(company, seed)
    injector.apply_errors(["X2"])
    duplicate, period = injector.issues
    assert duplicate.type == "duplicate_accounts"
    assert period.type == "period_misclassification"
    invoice_id = next(inv.invoice_id for inv in company.invoices if inv.invoice_id in period.affected_ids)
    assert invoice_id in duplicate.affected_ids
    rows = [row for row in company.ledger if row.invoice_id == invoice_id and row.payment_id is None]
    assert len(rows) == 4
    assert len({(row.account, row.debit_minor, row.credit_minor, row.currency) for row in rows}) == 2
    late = [row for row in rows if row.timestamp > company.period_end]
    assert len(late) == 2
    assert set(period.affected_ids) == {invoice_id, *(row.row_id for row in late)}
    assert all(row.row_id in duplicate.acceptable_evidence_sets[0] for row in rows)
    assert all(change.before_state["scenario"] == "X2" for change in injector.changes)
    assert_valid_issues(company, injector)


@pytest.mark.parametrize("count", range(13))
def test_every_issue_count_zero_through_twelve(count):
    company = SyntheticCompany(8911 + count, "issue_count", num_cycles=40, cycle_types=["full"])
    company.generate()
    injector = ErrorInjector(company, 8911 + count)
    injector.apply_errors((["E1", "E2", "E3", "E4"] * 3)[:count])
    assert len(injector.issues) == count
    families = []
    by_row = {row.row_id: row for row in company.ledger}
    for issue in injector.issues:
        families.append({by_row[value].invoice_id for value in issue.affected_ids if value in by_row})
    assert all(len(family) == 1 for family in families)
    assert len({next(iter(family)) for family in families}) == count
    assert_valid_issues(company, injector)


@pytest.mark.parametrize("seed", range(12))
def test_twelve_mixed_issues_have_existing_evidence_and_no_conflicts(seed):
    company = SyntheticCompany(17000 + seed, "mixed", num_cycles=50, cycle_types=["full", "split", "unpaid"])
    company.generate()
    injector = ErrorInjector(company, 17000 + seed)
    injector.apply_errors(["E1", "E2", "E3", "E4", "X1", "X2", "E1", "E2", "E3", "E4"])
    assert len(injector.issues) == 12
    assert_valid_issues(company, injector)


def test_invalid_error_requests_and_unavailable_candidates_are_atomic():
    company = SyntheticCompany(43, "atomic", num_cycles=20, cycle_types=["unpaid"])
    company.generate()
    injector = ErrorInjector(company, 43)
    before = deepcopy(company.__dict__)
    before_rng = injector.rng.getstate()
    for request in (["E1", "unknown"], ["X1"] * 7, ["E1", "E2"]):
        with pytest.raises(ValueError):
            injector.apply_errors(request)
        assert company.ledger == before["ledger"]
        assert company.manifest == before["manifest"]
        assert company._row_counter == before["_row_counter"]
        assert injector.issues == injector.changes == []
        assert injector.rng.getstate() == before_rng
    injector.apply_errors(["E1"] * 12)
    with pytest.raises(ValueError, match="12"):
        injector.apply_errors(["E1"])
    assert len(injector.issues) == 12


def test_fx_rates_are_exact_decimal_reciprocals_and_money_rounds_once():
    company = SyntheticCompany(792, "decimal")
    company.generate()
    rates = {(rate.date, rate.source_currency, rate.target_currency): rate.rate for rate in company.fx_rates}
    for rate in company.fx_rates:
        assert isinstance(rate.rate, Decimal)
        if rate.target_currency == "USD":
            inverse = rates[(rate.date, "USD", rate.source_currency)]
            assert inverse == (Decimal(1) / rate.rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    assert convert_fx(1, Decimal("1.5")) == 2
    assert convert_fx(101, Decimal("1.005")) == 102


def test_empty_truth_evidence_sets_are_rejected():
    with pytest.raises(ValidationError):
        TruthIssue(issue_id="i", type="partial_payment", affected_ids=["p"],
                   expected_amount_minor=1, currency="USD", acceptable_evidence_sets=[[]])


@pytest.mark.parametrize("seed", range(256))
def test_default_company_supports_twelve_independent_fx_issues(seed):
    company = SyntheticCompany(seed, "maximum_fx_capacity")
    company.generate()
    injector = ErrorInjector(company, seed)
    assert len({invoice.invoice_id for _, invoice in injector._receipts(foreign_only=True)}) >= 12
    injector.apply_errors(["E3"] * 12)
    assert len(injector.issues) == 12
    assert all(issue.type == "wrong_fx_or_date" for issue in injector.issues)
    assert_valid_issues(company, injector)


def test_explicit_refund_probability_override_preserves_all_refund_semantics():
    company = SyntheticCompany(14, "all_refunds", refund_probability=1.0)
    company.generate()
    originals = [invoice for invoice in company.invoices if invoice.document_type == "invoice"]
    notes = [invoice for invoice in company.invoices if invoice.document_type == "credit_note"]
    assert len(originals) == len(notes)
    assert len([pay for pay in company.payments if pay.direction == "refund"]) == len(notes)
    assert not ErrorInjector(company, 14)._receipts(foreign_only=True)


@pytest.mark.parametrize("seed", [14, 31, 118, 417])
@pytest.mark.parametrize("errors", [
    ["E1"] * 11 + ["E3"], ["E2"] * 11 + ["E3"],
    ["E4"] * 11 + ["E3"], ["X1"] * 6, ["X2"] * 5 + ["E3"] * 2,
])
def test_default_diversity_survives_worst_case_family_reservation(seed, errors):
    company = SyntheticCompany(seed, "ordered_capacity", num_cycles=20)
    company.generate()
    injector = ErrorInjector(company, seed)
    injector.apply_errors(errors)
    assert len(injector.issues) == 12
    assert_valid_issues(company, injector)


def test_legacy_provenance_loads_without_new_reproduction_metadata():
    payload = '{"episode_id":"legacy","seed":42,"created_at":"2025-01-31T23:59:59+00:00","changes":[]}'
    legacy = ProvenanceFile.model_validate_json(payload)
    assert legacy.generator_version == "1.0.0"
    assert legacy.generation_config == {}
    assert legacy.error_types == []
    current = legacy.model_copy(update={"generator_version": "2.0.0",
                                      "generation_config": {"num_cycles": 20},
                                      "error_types": ["X1", "E3"]})
    reloaded = ProvenanceFile.model_validate_json(current.model_dump_json())
    assert reloaded.generation_config == {"num_cycles": 20}
    assert reloaded.error_types == ["X1", "E3"]
    assert legacy.generation_config == {}
