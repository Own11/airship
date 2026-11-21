from typing import List, Dict, Any, Tuple
from decimal import Decimal
import random
import copy
from fintech_rl.generator.company import SyntheticCompany, ACCOUNTS
from fintech_rl.schema import LedgerRow, InvoiceDoc, PaymentDoc, TruthIssue, ProvenanceChange
from fintech_rl.scoring.tolerances import convert_fx


class ErrorInjector:
    """Injects 4 distinct error types and 2 interacting scenarios into a SyntheticCompany."""

    def __init__(self, company: SyntheticCompany, seed: int):
        self.company = company
        self.rng = random.Random(seed)
        self.issues: List[TruthIssue] = []
        self.changes: List[ProvenanceChange] = []
        self._issue_counter = 1

    def _next_issue_id(self) -> str:
        iid = f"ISSUE-{self._issue_counter:04d}"
        self._issue_counter += 1
        return iid

    def inject_e1_duplicate_accounts(self) -> bool:
        """
        E1: Duplicate accounting entry.
        A valid invoice or payment entry in ledger is duplicated (both debit & credit rows cloned),
        causing double-counting on the ledger compared to the supporting document.
        Discrepancy = amount of duplicated transaction.
        Evidence: [original row_ids, duplicated row_ids, doc_id].
        """
        # Find an invoice with ledger rows
        candidates = [inv for inv in self.company.invoices if any(r.invoice_id == inv.invoice_id for r in self.company.ledger)]
        if not candidates:
            return False
        inv = self.rng.choice(candidates)
        matching_rows = [r for r in self.company.ledger if r.invoice_id == inv.invoice_id and r.payment_id is None]
        if len(matching_rows) < 2:
            return False

        r_debit = [r for r in matching_rows if r.debit_minor > 0][0]
        r_credit = [r for r in matching_rows if r.credit_minor > 0][0]

        dup_r1_id = f"ROW-DUP-{self.rng.randint(10000, 99999)}"
        dup_r2_id = f"ROW-DUP-{self.rng.randint(10000, 99999)}"

        dup_r1 = LedgerRow(
            row_id=dup_r1_id,
            timestamp=r_debit.timestamp,
            account=r_debit.account,
            debit_minor=r_debit.debit_minor,
            credit_minor=0,
            currency=r_debit.currency,
            entity_id=r_debit.entity_id,
            invoice_id=r_debit.invoice_id,
            payment_id=None
        )
        dup_r2 = LedgerRow(
            row_id=dup_r2_id,
            timestamp=r_credit.timestamp,
            account=r_credit.account,
            debit_minor=0,
            credit_minor=r_credit.credit_minor,
            currency=r_credit.currency,
            entity_id=r_credit.entity_id,
            invoice_id=r_credit.invoice_id,
            payment_id=None
        )

        self.company.ledger.extend([dup_r1, dup_r2])

        issue_id = self._next_issue_id()
        affected = [r_debit.row_id, r_credit.row_id, dup_r1_id, dup_r2_id, inv.invoice_id]
        evidence_set = [dup_r1_id, dup_r2_id, inv.doc_id]

        issue = TruthIssue(
            issue_id=issue_id,
            type="duplicate_accounts",
            affected_ids=affected,
            expected_amount_minor=inv.total_minor,
            currency=inv.currency,
            acceptable_evidence_sets=[
                [dup_r1_id, dup_r2_id, inv.doc_id],
                [dup_r1_id, dup_r2_id, r_debit.row_id, r_credit.row_id, inv.doc_id]
            ]
        )
        self.issues.append(issue)

        change = ProvenanceChange(
            issue_id=issue_id,
            type="duplicate_accounts",
            affected_ids=affected,
            expected_amount_minor=inv.total_minor,
            currency=inv.currency,
            acceptable_evidence_sets=issue.acceptable_evidence_sets,
            description=f"Cloned ledger rows for invoice {inv.invoice_id} creating duplicate accounting entry.",
            before_state={"rows": [r_debit.row_id, r_credit.row_id]},
            after_state={"added_rows": [dup_r1_id, dup_r2_id]}
        )
        self.changes.append(change)
        return True

    def inject_e2_partial_payment(self) -> bool:
        """
        E2: Missed/incomplete payment allocation.
        A payment was made in full on payment document, but in the ledger only a partial amount was allocated,
        leaving an unreconciled remainder on AR.
        Discrepancy = omitted partial amount (payment.amount_minor - allocated_minor).
        Evidence: [payment_doc_id, payment_ledger_row_ids].
        """
        candidates = [p for p in self.company.payments if p.amount_minor > 1000]
        if not candidates:
            return False
        pay = self.rng.choice(candidates)
        # Find ledger rows for this payment
        p_rows = [r for r in self.company.ledger if r.payment_id == pay.payment_id]
        if len(p_rows) < 2:
            return False

        # Allocate only 60%
        unallocated_amt = pay.amount_minor // 3
        allocated_amt = pay.amount_minor - unallocated_amt

        for r in p_rows:
            if r.debit_minor > 0:
                r.debit_minor = allocated_amt
            if r.credit_minor > 0:
                r.credit_minor = allocated_amt

        issue_id = self._next_issue_id()
        affected = [pay.payment_id] + [r.row_id for r in p_rows]
        issue = TruthIssue(
            issue_id=issue_id,
            type="partial_payment",
            affected_ids=affected,
            expected_amount_minor=unallocated_amt,
            currency=pay.currency,
            acceptable_evidence_sets=[
                [pay.doc_id] + [r.row_id for r in p_rows]
            ]
        )
        self.issues.append(issue)

        change = ProvenanceChange(
            issue_id=issue_id,
            type="partial_payment",
            affected_ids=affected,
            expected_amount_minor=unallocated_amt,
            currency=pay.currency,
            acceptable_evidence_sets=issue.acceptable_evidence_sets,
            description=f"Underallocated payment {pay.payment_id} in ledger by {unallocated_amt} {pay.currency}.",
            before_state={"original_amount": pay.amount_minor},
            after_state={"allocated_amount": allocated_amt}
        )
        self.changes.append(change)
        return True

    def inject_e3_wrong_fx_or_date(self) -> bool:
        """
        E3: Wrong FX rate or date conversion.
        A foreign currency transaction was booked using an arbitrary stale or manipulated rate,
        causing discrepancy against the official fx.csv rate on transaction date.
        """
        # Find non-USD invoices
        candidates = [inv for inv in self.company.invoices if inv.currency != "USD"]
        if not candidates:
            return False
        inv = self.rng.choice(candidates)
        date_str = inv.issued_at[:10]

        # Official rate in fx.csv
        official_rate_rows = [f for f in self.company.fx_rates if f.date == date_str and f.source_currency == inv.currency and f.target_currency == "USD"]
        if not official_rate_rows:
            return False
        official_rate = official_rate_rows[0].rate

        # Fabricate faulty rate (+15% or -15%)
        bad_rate = Decimal(str(round(float(official_rate) * 1.15, 4)))
        expected_base = convert_fx(inv.total_minor, official_rate)
        bad_base = convert_fx(inv.total_minor, bad_rate)
        discrepancy = abs(bad_base - expected_base)

        # Alter the ledger rows for this invoice to use bad converted base currency amount or note
        # To show in ledger, we convert invoice AR/Revenue to base currency if not already or record the booking
        rows = [r for r in self.company.ledger if r.invoice_id == inv.invoice_id and r.payment_id is None]
        if not rows:
            return False

        for r in rows:
            # Change currency to USD and use bad converted amount
            r.currency = "USD"
            if r.debit_minor > 0:
                r.debit_minor = bad_base
            if r.credit_minor > 0:
                r.credit_minor = bad_base

        issue_id = self._next_issue_id()
        affected = [inv.invoice_id] + [r.row_id for r in rows]
        issue = TruthIssue(
            issue_id=issue_id,
            type="wrong_fx_or_date",
            affected_ids=affected,
            expected_amount_minor=discrepancy,
            currency="USD",
            acceptable_evidence_sets=[
                [inv.doc_id] + [r.row_id for r in rows]
            ]
        )
        self.issues.append(issue)

        change = ProvenanceChange(
            issue_id=issue_id,
            type="wrong_fx_or_date",
            affected_ids=affected,
            expected_amount_minor=discrepancy,
            currency="USD",
            acceptable_evidence_sets=issue.acceptable_evidence_sets,
            description=f"Applied wrong FX rate {bad_rate} instead of {official_rate} for {inv.invoice_id}.",
            before_state={"official_rate": str(official_rate), "expected_base": expected_base},
            after_state={"bad_rate": str(bad_rate), "bad_base": bad_base}
        )
        self.changes.append(change)
        return True

    def inject_e4_period_misclassification(self) -> bool:
        """
        E4: Period misclassification.
        A transaction occurring outside the reporting period (e.g., Feb 2025) is improperly backdated
        or recorded inside Jan 2025, or vice-versa.
        Discrepancy = transaction amount.
        """
        # Pick an invoice issued near end of month
        candidates = [inv for inv in self.company.invoices if inv.issued_at.startswith("2025-01-2")]
        if not candidates:
            return False
        inv = self.rng.choice(candidates)
        rows = [r for r in self.company.ledger if r.invoice_id == inv.invoice_id and r.payment_id is None]
        if not rows:
            return False

        # Shift the document date to 2025-02-05 (outside period), while ledger remains in Jan
        orig_inv_date = inv.issued_at
        inv.issued_at = "2025-02-05T11:00:00+00:00"

        issue_id = self._next_issue_id()
        affected = [inv.invoice_id] + [r.row_id for r in rows]
        issue = TruthIssue(
            issue_id=issue_id,
            type="period_misclassification",
            affected_ids=affected,
            expected_amount_minor=inv.total_minor,
            currency=inv.currency,
            acceptable_evidence_sets=[
                [inv.doc_id] + [r.row_id for r in rows]
            ]
        )
        self.issues.append(issue)

        change = ProvenanceChange(
            issue_id=issue_id,
            type="period_misclassification",
            affected_ids=affected,
            expected_amount_minor=inv.total_minor,
            currency=inv.currency,
            acceptable_evidence_sets=issue.acceptable_evidence_sets,
            description=f"Invoice {inv.invoice_id} belongs to February ({inv.issued_at}) but was recognized in January ledger.",
            before_state={"doc_date": orig_inv_date},
            after_state={"doc_date": inv.issued_at}
        )
        self.changes.append(change)
        return True

    def inject_x1_partial_fx_period_boundary(self) -> bool:
        """
        X1: Interacting scenario 1.
        Partial payment in foreign currency right on the period boundary.
        Combines foreign currency valuation + boundary timing + partial ledger allocation.
        """
        # Pick a foreign currency payment (EUR or GBP)
        candidates = [p for p in self.company.payments if p.currency in ("EUR", "GBP") and p.amount_minor > 1000]
        if not candidates:
            return False
        pay = self.rng.choice(candidates)
        rows = [r for r in self.company.ledger if r.payment_id == pay.payment_id]
        if len(rows) < 2:
            return False

        # Set payment timestamp right at the period cutoff boundary
        pay.timestamp = "2025-01-31T22:45:00+00:00"

        # Allocate partial amount (50% unallocated)
        unallocated_amt = pay.amount_minor // 2
        allocated_amt = pay.amount_minor - unallocated_amt

        for r in rows:
            r.timestamp = pay.timestamp
            if r.debit_minor > 0:
                r.debit_minor = allocated_amt
            if r.credit_minor > 0:
                r.credit_minor = allocated_amt

        issue_id = self._next_issue_id()
        affected = [pay.payment_id] + [r.row_id for r in rows]
        issue = TruthIssue(
            issue_id=issue_id,
            type="partial_payment",
            affected_ids=affected,
            expected_amount_minor=unallocated_amt,
            currency=pay.currency,
            acceptable_evidence_sets=[
                [pay.doc_id] + [r.row_id for r in rows]
            ]
        )
        self.issues.append(issue)

        change = ProvenanceChange(
            issue_id=issue_id,
            type="partial_payment",
            affected_ids=affected,
            expected_amount_minor=unallocated_amt,
            currency=pay.currency,
            acceptable_evidence_sets=issue.acceptable_evidence_sets,
            description=f"Interacting scenario X1: unallocated foreign currency payment {pay.payment_id} ({pay.currency}) on period boundary ({pay.timestamp}).",
            before_state={"full_amount": pay.amount_minor, "currency": pay.currency},
            after_state={"allocated": allocated_amt, "boundary_ts": pay.timestamp}
        )
        self.changes.append(change)
        return True

    def inject_x2_duplicate_and_period(self) -> bool:
        """
        X2: Interacting scenario 2.
        Duplicate entry AND period misclassification on the SAME invoice/transaction.
        An invoice belonging to February (outside reporting period) was improperly booked in January,
        and its ledger entries were also duplicated.
        """
        candidates = [inv for inv in self.company.invoices if inv.issued_at.startswith("2025-01-2")]
        if not candidates:
            return False
        inv = self.rng.choice(candidates)
        matching_rows = [r for r in self.company.ledger if r.invoice_id == inv.invoice_id and r.payment_id is None]
        if len(matching_rows) < 2:
            return False

        r_debit = [r for r in matching_rows if r.debit_minor > 0][0]
        r_credit = [r for r in matching_rows if r.credit_minor > 0][0]

        # 1. Period misclassification on this invoice: belongs to February
        orig_inv_date = inv.issued_at
        inv.issued_at = "2025-02-04T10:00:00+00:00"

        issue_p_id = self._next_issue_id()
        affected_p = [inv.invoice_id, r_debit.row_id, r_credit.row_id]
        issue_period = TruthIssue(
            issue_id=issue_p_id,
            type="period_misclassification",
            affected_ids=affected_p,
            expected_amount_minor=inv.total_minor,
            currency=inv.currency,
            acceptable_evidence_sets=[
                [inv.doc_id, r_debit.row_id, r_credit.row_id]
            ]
        )
        self.issues.append(issue_period)

        # 2. Duplicate entries cloned for the same out-of-period invoice
        dup_r1_id = f"ROW-DUP-{self.rng.randint(10000, 99999)}"
        dup_r2_id = f"ROW-DUP-{self.rng.randint(10000, 99999)}"

        dup_r1 = LedgerRow(
            row_id=dup_r1_id,
            timestamp=r_debit.timestamp,
            account=r_debit.account,
            debit_minor=r_debit.debit_minor,
            credit_minor=0,
            currency=r_debit.currency,
            entity_id=r_debit.entity_id,
            invoice_id=r_debit.invoice_id,
            payment_id=None
        )
        dup_r2 = LedgerRow(
            row_id=dup_r2_id,
            timestamp=r_credit.timestamp,
            account=r_credit.account,
            debit_minor=0,
            credit_minor=r_credit.credit_minor,
            currency=r_credit.currency,
            entity_id=r_credit.entity_id,
            invoice_id=r_credit.invoice_id,
            payment_id=None
        )
        self.company.ledger.extend([dup_r1, dup_r2])

        issue_dup_id = self._next_issue_id()
        affected_dup = [r_debit.row_id, r_credit.row_id, dup_r1_id, dup_r2_id, inv.invoice_id]
        issue_dup = TruthIssue(
            issue_id=issue_dup_id,
            type="duplicate_accounts",
            affected_ids=affected_dup,
            expected_amount_minor=inv.total_minor,
            currency=inv.currency,
            acceptable_evidence_sets=[
                [dup_r1_id, dup_r2_id, inv.doc_id],
                [dup_r1_id, dup_r2_id, r_debit.row_id, r_credit.row_id, inv.doc_id]
            ]
        )
        self.issues.append(issue_dup)

        change = ProvenanceChange(
            issue_id=issue_dup_id,
            type="duplicate_accounts",
            affected_ids=affected_dup,
            expected_amount_minor=inv.total_minor,
            currency=inv.currency,
            acceptable_evidence_sets=issue_dup.acceptable_evidence_sets,
            description=f"Interacting scenario X2: Cloned out-of-period invoice {inv.invoice_id}.",
            before_state={"rows": [r_debit.row_id, r_credit.row_id], "doc_date": orig_inv_date},
            after_state={"added_rows": [dup_r1_id, dup_r2_id], "doc_date": inv.issued_at}
        )
        self.changes.append(change)
        return True

    def apply_errors(self, error_types: List[str]):
        """Applies requested error types deterministically."""
        for et in error_types:
            if et == "E1" or et == "duplicate_accounts":
                self.inject_e1_duplicate_accounts()
            elif et == "E2" or et == "partial_payment":
                self.inject_e2_partial_payment()
            elif et == "E3" or et == "wrong_fx_or_date":
                self.inject_e3_wrong_fx_or_date()
            elif et == "E4" or et == "period_misclassification":
                self.inject_e4_period_misclassification()
            elif et == "X1":
                self.inject_x1_partial_fx_period_boundary()
            elif et == "X2":
                self.inject_x2_duplicate_and_period()
        # Sort ledger again deterministically
        self.company.ledger.sort(key=lambda r: (r.timestamp, r.row_id))
        self.company.manifest.n_records = len(self.company.ledger)
        self.company.manifest.n_documents = len(self.company.invoices) + len(self.company.payments)
