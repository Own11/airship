"""Controlled, non-overlapping financial errors with reproducible public proof."""
import copy
from decimal import Decimal, ROUND_HALF_UP
import random
from typing import Any, List

from fintech_rl.generator.company import SyntheticCompany, ACCOUNTS
from fintech_rl.identifiers import fx_record_id
from fintech_rl.schema import InvoiceDoc, LedgerRow, PaymentDoc, TruthIssue, ProvenanceChange
from fintech_rl.scoring.tolerances import convert_fx


_ERROR_ALIASES = {
    "E1": "E1", "duplicate_accounts": "E1",
    "E2": "E2", "partial_payment": "E2",
    "E3": "E3", "wrong_fx_or_date": "E3",
    "E4": "E4", "period_misclassification": "E4",
    "X1": "X1", "X2": "X2",
}
_ERROR_COST = {"E1": 1, "E2": 1, "E3": 1, "E4": 1, "X1": 2, "X2": 2}


class ErrorInjector:
    """Inject E1–E4 and two linked two-issue scenarios.

    Independent scenarios reserve the complete invoice family. A later injection
    cannot change evidence or amounts on which an earlier issue depends. X1/X2
    intentionally share a family internally and each emit two ordinary issues,
    preserving the public one-to-one matcher schema.
    """

    def __init__(self, company: SyntheticCompany, seed: int):
        self.company = company
        self.rng = random.Random(seed)
        self.issues: List[TruthIssue] = []
        self.changes: List[ProvenanceChange] = []
        self._issue_counter = 1
        self._reserved_invoices: set[str] = set()

    def _next_issue_id(self) -> str:
        issue_id = f"ISSUE-{self._issue_counter:04d}"
        self._issue_counter += 1
        return issue_id

    def _check_budget(self, count: int) -> None:
        if len(self.issues) + count > 12:
            raise ValueError("An episode supports at most 12 truth issues")

    def _invoices(self) -> list[InvoiceDoc]:
        returned = {inv.related_invoice_id for inv in self.company.invoices
                    if inv.document_type == "credit_note"}
        return [inv for inv in self.company.invoices
                if inv.document_type == "invoice"
                and inv.invoice_id not in returned
                and inv.invoice_id not in self._reserved_invoices]

    def _invoice_rows(self, invoice_id: str) -> list[LedgerRow]:
        return [row for row in self.company.ledger
                if row.invoice_id == invoice_id and row.payment_id is None]

    def _receipts(self, foreign_only: bool = False) -> list[tuple[PaymentDoc, InvoiceDoc]]:
        invoices = {inv.invoice_id: inv for inv in self._invoices()}
        return [(pay, invoices[pay.invoice_refs[0]]) for pay in self.company.payments
                if pay.direction == "receipt" and len(pay.invoice_refs) == 1
                and pay.invoice_refs[0] in invoices and pay.amount_minor > 1000
                and (not foreign_only or pay.currency != self.company.base_currency)]

    def _payment_rows(self, payment_id: str) -> list[LedgerRow]:
        return [row for row in self.company.ledger if row.payment_id == payment_id]

    @staticmethod
    def _snapshots(rows: list[LedgerRow]) -> list[dict[str, Any]]:
        return [row.model_dump() for row in rows]

    def _record(
        self, issue_type: str, affected: list[str], amount: int, currency: str,
        evidence: list[str], description: str, before: dict[str, Any], after: dict[str, Any],
    ) -> None:
        issue = TruthIssue(
            issue_id=self._next_issue_id(), type=issue_type, affected_ids=affected,
            expected_amount_minor=amount, currency=currency,
            acceptable_evidence_sets=[evidence],
        )
        self.issues.append(issue)
        self.changes.append(ProvenanceChange(
            **issue.model_dump(), description=description,
            before_state=before, after_state=after,
        ))

    def _finish(self) -> None:
        self.company.ledger.sort(key=lambda row: (row.timestamp, row.row_id))
        if self.company.manifest is None:
            raise ValueError("Generate the company before injecting errors")
        self.company.manifest.n_records = len(self.company.ledger)
        self.company.manifest.n_documents = len(self.company.invoices) + len(self.company.payments)
        if not 200 <= self.company.manifest.n_records <= 2000:
            raise ValueError("Injected episode violates the ledger record budget")
        if not 20 <= self.company.manifest.n_documents <= 200:
            raise ValueError("Injected episode violates the document budget")

    def _duplicate(self, invoice: InvoiceDoc, scenario: str) -> list[LedgerRow]:
        originals = self._invoice_rows(invoice.invoice_id)
        before = self._snapshots(originals)
        duplicates = [row.model_copy(update={"row_id": self.company._next_row_id()})
                      for row in originals]
        self.company.ledger.extend(duplicates)
        rows = originals + duplicates
        self._record(
            "duplicate_accounts", [invoice.invoice_id] + [row.row_id for row in rows],
            invoice.total_minor, invoice.currency,
            [invoice.doc_id] + [row.row_id for row in rows],
            f"{scenario}: duplicated the balanced recognition of {invoice.invoice_id}.",
            {"scenario": scenario, "rows": before, "invoice": invoice.model_dump()},
            {"scenario": scenario, "rows": self._snapshots(rows)},
        )
        self._reserved_invoices.add(invoice.invoice_id)
        return duplicates

    def inject_e1_duplicate_accounts(self) -> bool:
        self._check_budget(1)
        candidates = [inv for inv in self._invoices() if len(self._invoice_rows(inv.invoice_id)) == 2]
        if not candidates:
            return False
        self._duplicate(self.rng.choice(candidates), "E1")
        self._finish()
        return True

    def inject_e2_partial_payment(self) -> bool:
        self._check_budget(1)
        candidates = self._receipts()
        if not candidates:
            return False
        pay, invoice = self.rng.choice(candidates)
        rows = self._payment_rows(pay.payment_id)
        before = {"scenario": "E2", "payment": pay.model_dump(), "rows": self._snapshots(rows)}
        missing = pay.amount_minor // 3
        allocated = pay.amount_minor - missing
        for row in rows:
            if row.debit_minor:
                row.debit_minor = allocated
            else:
                row.credit_minor = allocated
        self._record(
            "partial_payment", [pay.payment_id] + [row.row_id for row in rows],
            missing, pay.currency, [invoice.doc_id, pay.doc_id] + [row.row_id for row in rows],
            f"E2: only {allocated} of payment {pay.payment_id} was allocated to receivables.",
            before, {"scenario": "E2", "rows": self._snapshots(rows), "allocated_amount_minor": allocated},
        )
        self._reserved_invoices.add(invoice.invoice_id)
        self._finish()
        return True

    def _fx_settlement(
        self, pay: PaymentDoc, invoice: InvoiceDoc, allocated: int,
        scenario: str, boundary: bool,
    ) -> tuple[list[LedgerRow], list[LedgerRow], Decimal, str, dict[str, Any]]:
        source_rows = self._payment_rows(pay.payment_id)
        before = {"scenario": scenario, "payment": pay.model_dump(), "rows": self._snapshots(source_rows)}
        if boundary:
            pay.timestamp = self.company.period_end
        date = pay.timestamp[:10]
        official = next(rate.rate for rate in self.company.fx_rates
                        if rate.date == date and rate.source_currency == pay.currency
                        and rate.target_currency == self.company.base_currency)
        bad_rate = (official * Decimal("1.15")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        base_amount = convert_fx(allocated, bad_rate)
        # AR stays in the invoice's currency. FX clearing links source settlement
        # to the base-currency bank receipt, with a balanced pair in each currency.
        for row in source_rows:
            row.timestamp = pay.timestamp
            if row.debit_minor:
                row.account = ACCOUNTS["FX_CLEARING"]
                row.debit_minor = allocated
            else:
                row.credit_minor = allocated
        base_rows = self.company._add_pair(
            pay.timestamp, ACCOUNTS["CASH"], ACCOUNTS["FX_CLEARING"], base_amount,
            self.company.base_currency, invoice.entity_id, invoice.invoice_id, pay.payment_id,
        )
        return source_rows, base_rows, official, str(bad_rate), before

    def _record_fx(
        self, pay: PaymentDoc, invoice: InvoiceDoc, source_rows: list[LedgerRow],
        base_rows: list[LedgerRow], allocated: int, official: Decimal,
        bad_rate: str, scenario: str, before: dict[str, Any],
    ) -> None:
        rows = source_rows + base_rows
        actual = next(row.debit_minor for row in base_rows if row.account == ACCOUNTS["CASH"])
        expected = convert_fx(allocated, official)
        rate_id = fx_record_id(pay.timestamp[:10], pay.currency, self.company.base_currency)
        self._record(
            "wrong_fx_or_date", [pay.payment_id, invoice.invoice_id] + [row.row_id for row in rows],
            abs(actual - expected), self.company.base_currency,
            [invoice.doc_id, pay.doc_id] + [row.row_id for row in rows] + [rate_id],
            f"{scenario}: converted allocated payment {pay.payment_id} using {bad_rate} instead of {official}.",
            before, {"scenario": scenario, "payment": pay.model_dump(), "rows": self._snapshots(rows),
                     "allocated_amount_minor": allocated, "official_rate": str(official),
                     "bad_rate": bad_rate, "expected_base_minor": expected, "actual_base_minor": actual},
        )

    def inject_e3_wrong_fx_or_date(self) -> bool:
        self._check_budget(1)
        candidates = self._receipts(foreign_only=True)
        if not candidates:
            return False
        pay, invoice = self.rng.choice(candidates)
        source, base, official, bad_rate, before = self._fx_settlement(
            pay, invoice, pay.amount_minor, "E3", boundary=False,
        )
        self._record_fx(pay, invoice, source, base, pay.amount_minor, official, bad_rate, "E3", before)
        self._reserved_invoices.add(invoice.invoice_id)
        self._finish()
        return True

    def inject_e4_period_misclassification(self) -> bool:
        self._check_budget(1)
        candidates = [inv for inv in self._invoices() if len(self._invoice_rows(inv.invoice_id)) == 2]
        if not candidates:
            return False
        invoice = self.rng.choice(candidates)
        rows = self._invoice_rows(invoice.invoice_id)
        before = {"scenario": "E4", "invoice": invoice.model_dump(), "rows": self._snapshots(rows)}
        for row in rows:
            row.timestamp = "2025-02-01T00:00:00+00:00"
        self._record(
            "period_misclassification", [invoice.invoice_id] + [row.row_id for row in rows],
            invoice.total_minor, invoice.currency, [invoice.doc_id] + [row.row_id for row in rows],
            f"E4: January invoice {invoice.invoice_id} was recognized in the following period.",
            before, {"scenario": "E4", "rows": self._snapshots(rows)},
        )
        self._reserved_invoices.add(invoice.invoice_id)
        self._finish()
        return True

    def inject_x1_partial_fx_period_boundary(self) -> bool:
        self._check_budget(2)
        candidates = self._receipts(foreign_only=True)
        if not candidates:
            return False
        pay, invoice = self.rng.choice(candidates)
        missing = pay.amount_minor // 2
        allocated = pay.amount_minor - missing
        source, base, official, bad_rate, before = self._fx_settlement(
            pay, invoice, allocated, "X1", boundary=True,
        )
        self._record(
            "partial_payment", [pay.payment_id] + [row.row_id for row in source],
            missing, pay.currency, [invoice.doc_id, pay.doc_id] + [row.row_id for row in source],
            f"X1: partial source-currency allocation of {pay.payment_id} at the reporting boundary; its converted settlement also uses wrong FX.",
            before, {"scenario": "X1", "payment": pay.model_dump(),
                     "rows": self._snapshots(source), "allocated_amount_minor": allocated},
        )
        self._record_fx(pay, invoice, source, base, allocated, official, bad_rate, "X1", before)
        self._reserved_invoices.add(invoice.invoice_id)
        self._finish()
        return True

    def inject_x2_duplicate_and_period(self) -> bool:
        self._check_budget(2)
        candidates = [inv for inv in self._invoices() if len(self._invoice_rows(inv.invoice_id)) == 2]
        if not candidates:
            return False
        invoice = self.rng.choice(candidates)
        duplicates = self._duplicate(invoice, "X2")
        before = {"scenario": "X2", "invoice": invoice.model_dump(), "rows": self._snapshots(duplicates)}
        for row in duplicates:
            row.timestamp = "2025-02-01T00:00:00+00:00"
        self._record(
            "period_misclassification", [invoice.invoice_id] + [row.row_id for row in duplicates],
            invoice.total_minor, invoice.currency, [invoice.doc_id] + [row.row_id for row in duplicates],
            f"X2: the duplicate recognition of {invoice.invoice_id} was posted to the following period.",
            before, {"scenario": "X2", "rows": self._snapshots(duplicates)},
        )
        self._finish()
        return True

    def apply_errors(self, error_types: list[str]) -> None:
        """Apply a validated batch atomically; never silently drop an error.

        The limit counts emitted issues (X1 and X2 each cost two), rather than
        scenario names. Invalid requests and exhausted candidates leave the
        company, RNG, truth and provenance unchanged.
        """
        if not isinstance(error_types, (list, tuple)):
            raise ValueError("error_types must be a sequence of supported error names")
        if any(not isinstance(name, str) or name not in _ERROR_ALIASES for name in error_types):
            raise ValueError("Unknown error type")
        normalized = [_ERROR_ALIASES[name] for name in error_types]
        self._check_budget(sum(_ERROR_COST[name] for name in normalized))
        methods = {
            "E1": self.inject_e1_duplicate_accounts, "E2": self.inject_e2_partial_payment,
            "E3": self.inject_e3_wrong_fx_or_date, "E4": self.inject_e4_period_misclassification,
            "X1": self.inject_x1_partial_fx_period_boundary, "X2": self.inject_x2_duplicate_and_period,
        }
        company_state = copy.deepcopy(self.company.__dict__)
        issue_state = copy.deepcopy((self.issues, self.changes, self._reserved_invoices))
        random_state = self.rng.getstate()
        issue_counter = self._issue_counter
        try:
            for name in normalized:
                if not methods[name]():
                    raise ValueError(f"No eligible untouched transaction for {name}")
            self._finish()
        except ValueError:
            self.company.__dict__.clear()
            self.company.__dict__.update(company_state)
            self.issues, self.changes, self._reserved_invoices = issue_state
            self.rng.setstate(random_state)
            self._issue_counter = issue_counter
            raise
