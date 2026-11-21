"""Deterministic, balanced synthetic sales, settlements and legitimate returns."""
from decimal import Decimal, ROUND_HALF_UP
import math
import random
from typing import List, Sequence

from fintech_rl.schema import (
    Manifest, LedgerRow, InvoiceDoc, InvoiceLineItem, PaymentDoc, FXRateRow,
    AccountingPolicy, RoundingRules,
)


CURRENCIES = ["USD", "EUR", "GBP"]
ENTITIES = [
    "ENT-NEXUS-CORP", "ENT-AURORA-LOGISTICS", "ENT-CYBER-DYNAMICS",
    "ENT-SOLARIS-TRADING", "ENT-VORTEX-MEDIA", "ENT-ZENITH-SUPPLY",
    "ENT-TITAN-CONSULTING", "ENT-ORION-RETAIL", "ENT-APEX-SOLUTIONS",
    "ENT-HORIZON-ENERGY", "ENT-STELLAR-INDUSTRIES", "ENT-ALPHA-NETWORKS",
]
ACCOUNTS = {
    "CASH": "1010-CASH",
    "AR": "1200-ACCOUNTS-RECEIVABLE",
    "AP": "2010-ACCOUNTS-PAYABLE",
    "REVENUE": "4010-SALES-REVENUE",
    "EXPENSE": "5010-OPERATING-EXPENSES",
    "FX_GAIN_LOSS": "7010-FX-GAIN-LOSS",
    "FX_CLEARING": "1090-FX-CLEARING",
}
_DOCS_PER_CYCLE = {"full": 2, "split": 3, "unpaid": 1, "refund": 4}


class SyntheticCompany:
    """Generate one company using only an instance-local seeded random source.

    ``cycle_types`` restricts business scenarios and samples them uniformly. When
    omitted, ``refund_probability`` selects returns; other cycles share the rest
    of the probability equally. Configurations reserve their worst-case document
    budget before generation, so no retry loop or silent truncation is needed.
    Defaults include a shuffled core of 18 full/split cycles (six per currency),
    providing 12 independent foreign receipt families for the maximum error
    budget. Explicit cycle types or a different refund probability disable this
    coverage core and may be incompatible with particular requested errors.
    """

    def __init__(
        self, seed: int, episode_id: str, clean_mode: bool = False, *,
        num_cycles: int | None = None, cycle_types: Sequence[str] | None = None,
        refund_probability: float = 0.15,
    ):
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("seed must be an integer")
        if num_cycles is not None and (
            isinstance(num_cycles, bool) or not isinstance(num_cycles, int)
            or not 20 <= num_cycles <= 100
        ):
            raise ValueError("num_cycles must be an integer between 20 and 100")
        if cycle_types is not None:
            if not isinstance(cycle_types, Sequence) or isinstance(cycle_types, (str, bytes)):
                raise ValueError("cycle_types must be a non-empty sequence of cycle names")
            cycle_types = tuple(cycle_types)
            if not cycle_types or any(not isinstance(t, str) or t not in _DOCS_PER_CYCLE for t in cycle_types):
                raise ValueError("cycle_types must contain full, split, unpaid or refund")
        if (
            isinstance(refund_probability, bool)
            or not isinstance(refund_probability, (float, int))
            or not math.isfinite(refund_probability)
            or not 0 <= refund_probability <= 1
        ):
            raise ValueError("refund_probability must be between zero and one")
        possible_types = cycle_types or tuple(_DOCS_PER_CYCLE)
        max_cycles = num_cycles if num_cycles is not None else 50
        if max_cycles * max(_DOCS_PER_CYCLE[t] for t in possible_types) > 200:
            raise ValueError("num_cycles and cycle_types exceed the 200 document budget")

        self.seed = seed
        self.rng = random.Random(seed)
        self.episode_id = episode_id
        self.clean_mode = clean_mode
        self.num_cycles = num_cycles
        self.cycle_types = cycle_types
        self.refund_probability = refund_probability
        self.base_currency = "USD"
        self.timezone = "+00:00"
        self.period_start = "2025-01-01T00:00:00+00:00"
        self.period_end = "2025-01-31T23:59:59+00:00"
        self.policy = AccountingPolicy(
            fx_rate_date_rule="transaction_date",
            period_boundary_rule="transaction_timestamp", rounding="nearest",
        )
        self.manifest: Manifest | None = None
        self.ledger: List[LedgerRow] = []
        self.invoices: List[InvoiceDoc] = []
        self.payments: List[PaymentDoc] = []
        self.fx_rates: List[FXRateRow] = []
        self._row_counter = 1
        self._doc_counter = 1

    def _next_row_id(self) -> str:
        row_id = f"ROW-{self._row_counter:05d}"
        self._row_counter += 1
        return row_id

    def _next_doc_id(self, prefix: str = "DOC") -> str:
        doc_id = f"{prefix}-{self._doc_counter:05d}"
        self._doc_counter += 1
        return doc_id

    def _add_pair(
        self, timestamp: str, debit_account: str, credit_account: str,
        amount: int, currency: str, entity_id: str | None,
        invoice_id: str | None = None, payment_id: str | None = None,
    ) -> list[LedgerRow]:
        common = dict(timestamp=timestamp, currency=currency, entity_id=entity_id,
                      invoice_id=invoice_id, payment_id=payment_id)
        rows = [
            LedgerRow(row_id=self._next_row_id(), account=debit_account,
                      debit_minor=amount, credit_minor=0, **common),
            LedgerRow(row_id=self._next_row_id(), account=credit_account,
                      debit_minor=0, credit_minor=amount, **common),
        ]
        self.ledger.extend(rows)
        return rows

    def _receipt(self, invoice: InvoiceDoc, payment_id: str, timestamp: str, amount: int) -> None:
        self.payments.append(PaymentDoc(
            doc_id=self._next_doc_id("DOC-PAY"), payment_id=payment_id,
            timestamp=timestamp, currency=invoice.currency, amount_minor=amount,
            invoice_refs=[invoice.invoice_id],
        ))
        self._add_pair(timestamp, ACCOUNTS["CASH"], ACCOUNTS["AR"], amount,
                       invoice.currency, invoice.entity_id, invoice.invoice_id, payment_id)

    def _return(self, invoice: InvoiceDoc, cycle_index: int, return_day: int) -> None:
        # A credit note reverses all or part of the sale; a cash refund settles it.
        amount = max(1, invoice.total_minor // self.rng.choice([1, 2, 4]))
        note_timestamp = f"2025-01-{return_day:02d}T10:00:00+00:00"
        refund_timestamp = f"2025-01-{return_day:02d}T11:00:00+00:00"
        note_id = f"CN-2025-{5000 + cycle_index}"
        note = InvoiceDoc(
            doc_id=self._next_doc_id("DOC-CN"), invoice_id=note_id,
            entity_id=invoice.entity_id, issued_at=note_timestamp,
            due_at=refund_timestamp, currency=invoice.currency, total_minor=amount,
            document_type="credit_note", related_invoice_id=invoice.invoice_id,
            line_items=[InvoiceLineItem(
                item_id=f"RETURN-{cycle_index}", description="Agreed return of goods and services",
                quantity=1, unit_price_minor=amount, total_minor=amount,
            )],
        )
        self.invoices.append(note)
        self._add_pair(note_timestamp, ACCOUNTS["REVENUE"], ACCOUNTS["AR"], amount,
                       invoice.currency, invoice.entity_id, note_id)
        payment_id = f"REFUND-2025-{6000 + cycle_index}"
        self.payments.append(PaymentDoc(
            doc_id=self._next_doc_id("DOC-REFUND"), payment_id=payment_id,
            timestamp=refund_timestamp, currency=invoice.currency,
            amount_minor=amount, invoice_refs=[note_id], direction="refund",
        ))
        self._add_pair(refund_timestamp, ACCOUNTS["AR"], ACCOUNTS["CASH"], amount,
                       invoice.currency, invoice.entity_id, note_id, payment_id)

    def generate(self) -> None:
        # Reusing the generator is equivalent to constructing it again.
        self.rng = random.Random(self.seed)
        self.ledger.clear()
        self.invoices.clear()
        self.payments.clear()
        self.fx_rates.clear()
        self._row_counter = self._doc_counter = 1
        self.manifest = None
        quantum = Decimal("0.0001")
        for day in range(1, 32):
            date = f"2025-01-{day:02d}"
            for source, low, high in [("EUR", 10600, 11200), ("GBP", 12600, 13200)]:
                rate = Decimal(self.rng.randint(low, high)) / Decimal(10000)
                inverse = (Decimal(1) / rate).quantize(quantum, rounding=ROUND_HALF_UP)
                self.fx_rates.extend([
                    FXRateRow(date=date, source_currency=source, target_currency="USD", rate=rate),
                    FXRateRow(date=date, source_currency="USD", target_currency=source, rate=inverse),
                ])

        num_cycles = self.num_cycles if self.num_cycles is not None else self.rng.randint(40, 50)
        coverage = {}
        if self.cycle_types is None and self.refund_probability == 0.15:
            # Reserve ordinary business diversity, rather than retrying until a
            # particular seed happens to support twelve independent FX issues.
            core = [(currency, kind) for currency in CURRENCIES
                    for kind in ("full", "split") for _ in range(3)]
            self.rng.shuffle(core)
            coverage = dict(zip(self.rng.sample(range(num_cycles), len(core)), core))
        for i in range(num_cycles):
            entity = self.rng.choice(ENTITIES)
            currency = coverage[i][0] if i in coverage else self.rng.choice(CURRENCIES)
            day = self.rng.randint(2, 28)
            hour = self.rng.randint(8, 17)
            minute = self.rng.randint(10, 50)
            timestamp = f"2025-01-{day:02d}T{hour:02d}:{minute:02d}:00+00:00"
            items = []
            for item_index in range(self.rng.randint(1, 3)):
                quantity = self.rng.randint(1, 10)
                price = self.rng.randint(50, 1000) * 100
                items.append(InvoiceLineItem(
                    item_id=f"ITEM-{i}-{item_index + 1}",
                    description=f"Standard Goods & Services {item_index + 1}",
                    quantity=quantity, unit_price_minor=price, total_minor=quantity * price,
                ))
            amount = sum(item.total_minor for item in items)
            invoice = InvoiceDoc(
                doc_id=self._next_doc_id("DOC-INV"), invoice_id=f"INV-2025-{1000 + i}",
                entity_id=entity, issued_at=timestamp,
                due_at=f"2025-02-{min(day, 25):02d}T18:00:00+00:00",
                currency=currency, total_minor=amount, line_items=items,
            )
            self.invoices.append(invoice)
            self._add_pair(timestamp, ACCOUNTS["AR"], ACCOUNTS["REVENUE"], amount,
                           currency, entity, invoice.invoice_id)
            if i in coverage:
                cycle_type = coverage[i][1]
            elif self.cycle_types is None:
                residual = (1 - self.refund_probability) / 3
                cycle_type = self.rng.choices(
                    ["full", "split", "unpaid", "refund"],
                    weights=[residual, residual, residual, self.refund_probability], k=1,
                )[0]
            else:
                cycle_type = self.rng.choice(self.cycle_types)
            if cycle_type in ("full", "refund"):
                pay_day = min(30, day + self.rng.randint(1, 3))
                pay_timestamp = f"2025-01-{pay_day:02d}T{hour:02d}:{minute:02d}:00+00:00"
                self._receipt(invoice, f"PAY-2025-{2000 + i}", pay_timestamp, amount)
                if cycle_type == "refund":
                    self._return(invoice, i, min(31, pay_day + 1))
            elif cycle_type == "split":
                first = amount // 2
                self._receipt(invoice, f"PAY-2025-{3000 + i * 2}",
                              f"2025-01-{min(30, day + 1):02d}T10:00:00+00:00", first)
                self._receipt(invoice, f"PAY-2025-{3001 + i * 2}",
                              f"2025-01-{min(30, day + 3):02d}T14:00:00+00:00", amount - first)

        # Actual row counts, including unpaid/split/return cases, determine a
        # bounded number of distinct routine expenses; no copied ledger rows.
        expense_count = max(10, (200 - len(self.ledger) + 1) // 2)
        for index in range(expense_count):
            day = index % 27 + 1
            hour = 8 + index // 27
            timestamp = f"2025-01-{day:02d}T{hour:02d}:30:00+00:00"
            amount = 50000 if index % 4 == 0 else self.rng.randint(200, 1500) * 100
            self._add_pair(timestamp, ACCOUNTS["EXPENSE"], ACCOUNTS["CASH"], amount,
                           self.base_currency, self.rng.choice(ENTITIES))
        self.ledger.sort(key=lambda row: (row.timestamp, row.row_id))
        n_documents = len(self.invoices) + len(self.payments)
        if not 200 <= len(self.ledger) <= 2000 or not 20 <= n_documents <= 200:
            raise ValueError("Generated episode violates record or document bounds")
        self.manifest = Manifest(
            schema_version="1.0.0", episode_id=self.episode_id,
            base_currency=self.base_currency, period_start=self.period_start,
            period_end=self.period_end, timezone=self.timezone,
            n_records=len(self.ledger), n_documents=n_documents, rounding_rules=RoundingRules(),
        )
