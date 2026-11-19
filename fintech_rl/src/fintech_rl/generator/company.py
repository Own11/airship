from decimal import Decimal
import random
from typing import List, Dict, Any, Tuple
from fintech_rl.schema import (
    Manifest, LedgerRow, InvoiceDoc, InvoiceLineItem, PaymentDoc, FXRateRow, AccountingPolicy, RoundingRules
)


CURRENCIES = ["USD", "EUR", "GBP"]
ENTITIES = [
    "ENT-NEXUS-CORP", "ENT-AURORA-LOGISTICS", "ENT-CYBER-DYNAMICS",
    "ENT-SOLARIS-TRADING", "ENT-VORTEX-MEDIA", "ENT-ZENITH-SUPPLY",
    "ENT-TITAN-CONSULTING", "ENT-ORION-RETAIL", "ENT-APEX-SOLUTIONS",
    "ENT-HORIZON-ENERGY", "ENT-STELLAR-INDUSTRIES", "ENT-ALPHA-NETWORKS"
]

ACCOUNTS = {
    "CASH": "1010-CASH",
    "AR": "1200-ACCOUNTS-RECEIVABLE",
    "AP": "2010-ACCOUNTS-PAYABLE",
    "REVENUE": "4010-SALES-REVENUE",
    "EXPENSE": "5010-OPERATING-EXPENSES",
    "FX_GAIN_LOSS": "7010-FX-GAIN-LOSS"
}


class SyntheticCompany:
    """Generates fully consistent, clean accounting records for an episode."""

    def __init__(self, seed: int, episode_id: str, clean_mode: bool = False):
        self.rng = random.Random(seed)
        self.episode_id = episode_id
        self.clean_mode = clean_mode

        self.base_currency = "USD"
        self.timezone = "+00:00"
        self.period_start = "2025-01-01T00:00:00+00:00"
        self.period_end = "2025-01-31T23:59:59+00:00"

        self.policy = AccountingPolicy(
            fx_rate_date_rule="transaction_date",
            period_boundary_rule="transaction_timestamp",
            rounding="nearest"
        )
        self.manifest: Manifest = None
        self.ledger: List[LedgerRow] = []
        self.invoices: List[InvoiceDoc] = []
        self.payments: List[PaymentDoc] = []
        self.fx_rates: List[FXRateRow] = []

        self._row_counter = 1
        self._doc_counter = 1

    def _next_row_id(self) -> str:
        rid = f"ROW-{self._row_counter:05d}"
        self._row_counter += 1
        return rid

    def _next_doc_id(self, prefix: str = "DOC") -> str:
        did = f"{prefix}-{self._doc_counter:05d}"
        self._doc_counter += 1
        return did

    def generate(self) -> None:
        # 1. FX Rates table for Jan 2025
        fx_map: Dict[Tuple[str, str, str], Decimal] = {}
        for day in range(1, 32):
            dt = f"2025-01-{day:02d}"
            # EUR/USD ~ 1.05 to 1.12
            eur_usd = Decimal(str(round(1.05 + self.rng.uniform(0.01, 0.07), 4)))
            # GBP/USD ~ 1.25 to 1.32
            gbp_usd = Decimal(str(round(1.25 + self.rng.uniform(0.01, 0.07), 4)))

            self.fx_rates.append(FXRateRow(date=dt, source_currency="EUR", target_currency="USD", rate=eur_usd))
            self.fx_rates.append(FXRateRow(date=dt, source_currency="USD", target_currency="EUR", rate=Decimal(str(round(1 / float(eur_usd), 4)))))

            self.fx_rates.append(FXRateRow(date=dt, source_currency="GBP", target_currency="USD", rate=gbp_usd))
            self.fx_rates.append(FXRateRow(date=dt, source_currency="USD", target_currency="GBP", rate=Decimal(str(round(1 / float(gbp_usd), 4)))))

            fx_map[(dt, "EUR", "USD")] = eur_usd
            fx_map[(dt, "GBP", "USD")] = gbp_usd
            fx_map[(dt, "USD", "USD")] = Decimal("1.0")

        # 2. Generate transactions: 40 to 80 business cycles (each creates invoices, payments, balanced ledger entries)
        num_cycles = self.rng.randint(40, 75)
        
        for i in range(num_cycles):
            entity = self.rng.choice(ENTITIES)
            curr = self.rng.choice(CURRENCIES)
            day = self.rng.randint(2, 28)
            time_h = self.rng.randint(8, 17)
            time_m = self.rng.randint(10, 50)
            inv_ts = f"2025-01-{day:02d}T{time_h:02d}:{time_m:02d}:00+00:00"
            due_ts = f"2025-02-{min(day, 25):02d}T18:00:00+00:00"

            # Create invoice
            inv_id = f"INV-2025-{1000 + i}"
            inv_doc_id = self._next_doc_id("DOC-INV")
            
            # Line items
            num_items = self.rng.randint(1, 3)
            items = []
            inv_total = 0
            for itm in range(num_items):
                qty = self.rng.randint(1, 10)
                unit_p = self.rng.randint(50, 1000) * 100 # minor units
                tot = qty * unit_p
                items.append(InvoiceLineItem(
                    item_id=f"ITEM-{i}-{itm+1}",
                    description=f"Standard Goods & Services {itm+1}",
                    quantity=qty,
                    unit_price_minor=unit_p,
                    total_minor=tot
                ))
                inv_total += tot

            inv_doc = InvoiceDoc(
                doc_id=inv_doc_id,
                invoice_id=inv_id,
                entity_id=entity,
                issued_at=inv_ts,
                due_at=due_ts,
                currency=curr,
                total_minor=inv_total,
                line_items=items
            )
            self.invoices.append(inv_doc)

            # Balanced ledger entries for invoice (AR Debit, Revenue Credit)
            # Both sides in same currency, exact match
            r1 = self._next_row_id()
            r2 = self._next_row_id()
            self.ledger.append(LedgerRow(
                row_id=r1,
                timestamp=inv_ts,
                account=ACCOUNTS["AR"],
                debit_minor=inv_total,
                credit_minor=0,
                currency=curr,
                entity_id=entity,
                invoice_id=inv_id,
                payment_id=None
            ))
            self.ledger.append(LedgerRow(
                row_id=r2,
                timestamp=inv_ts,
                account=ACCOUNTS["REVENUE"],
                debit_minor=0,
                credit_minor=inv_total,
                currency=curr,
                entity_id=entity,
                invoice_id=inv_id,
                payment_id=None
            ))

            # Realistic distractions: some paid in full, some split in 2 payments, some delayed
            cycle_type = self.rng.choice(["full", "split", "unpaid"])
            if cycle_type == "full":
                pay_day = min(30, day + self.rng.randint(1, 3))
                pay_ts = f"2025-01-{pay_day:02d}T{time_h:02d}:{time_m:02d}:00+00:00"
                pay_id = f"PAY-2025-{2000 + i}"
                pay_doc_id = self._next_doc_id("DOC-PAY")

                pay_doc = PaymentDoc(
                    doc_id=pay_doc_id,
                    payment_id=pay_id,
                    timestamp=pay_ts,
                    currency=curr,
                    amount_minor=inv_total,
                    invoice_refs=[inv_id]
                )
                self.payments.append(pay_doc)

                # Balanced ledger entries for payment (Cash Debit, AR Credit)
                pr1 = self._next_row_id()
                pr2 = self._next_row_id()
                self.ledger.append(LedgerRow(
                    row_id=pr1,
                    timestamp=pay_ts,
                    account=ACCOUNTS["CASH"],
                    debit_minor=inv_total,
                    credit_minor=0,
                    currency=curr,
                    entity_id=entity,
                    invoice_id=inv_id,
                    payment_id=pay_id
                ))
                self.ledger.append(LedgerRow(
                    row_id=pr2,
                    timestamp=pay_ts,
                    account=ACCOUNTS["AR"],
                    debit_minor=0,
                    credit_minor=inv_total,
                    currency=curr,
                    entity_id=entity,
                    invoice_id=inv_id,
                    payment_id=pay_id
                ))

            elif cycle_type == "split":
                # Legal split payment: 50% on pay_day1, 50% on pay_day2
                half1 = inv_total // 2
                half2 = inv_total - half1

                pday1 = min(28, day + 1)
                pday2 = min(30, day + 3)
                pts1 = f"2025-01-{pday1:02d}T10:00:00+00:00"
                pts2 = f"2025-01-{pday2:02d}T14:00:00+00:00"

                pid1 = f"PAY-2025-{3000 + i*2}"
                pid2 = f"PAY-2025-{3000 + i*2 + 1}"

                self.payments.append(PaymentDoc(
                    doc_id=self._next_doc_id("DOC-PAY"),
                    payment_id=pid1,
                    timestamp=pts1,
                    currency=curr,
                    amount_minor=half1,
                    invoice_refs=[inv_id]
                ))
                self.payments.append(PaymentDoc(
                    doc_id=self._next_doc_id("DOC-PAY"),
                    payment_id=pid2,
                    timestamp=pts2,
                    currency=curr,
                    amount_minor=half2,
                    invoice_refs=[inv_id]
                ))

                self.ledger.append(LedgerRow(
                    row_id=self._next_row_id(), timestamp=pts1, account=ACCOUNTS["CASH"],
                    debit_minor=half1, credit_minor=0, currency=curr, entity_id=entity, invoice_id=inv_id, payment_id=pid1
                ))
                self.ledger.append(LedgerRow(
                    row_id=self._next_row_id(), timestamp=pts1, account=ACCOUNTS["AR"],
                    debit_minor=0, credit_minor=half1, currency=curr, entity_id=entity, invoice_id=inv_id, payment_id=pid1
                ))
                self.ledger.append(LedgerRow(
                    row_id=self._next_row_id(), timestamp=pts2, account=ACCOUNTS["CASH"],
                    debit_minor=half2, credit_minor=0, currency=curr, entity_id=entity, invoice_id=inv_id, payment_id=pid2
                ))
                self.ledger.append(LedgerRow(
                    row_id=self._next_row_id(), timestamp=pts2, account=ACCOUNTS["AR"],
                    debit_minor=0, credit_minor=half2, currency=curr, entity_id=entity, invoice_id=inv_id, payment_id=pid2
                ))

        # Add some regular expenses (e.g. utilities, rent)
        for exp_i in range(10):
            exp_day = (exp_i * 3) % 27 + 1
            exp_ts = f"2025-01-{exp_day:02d}T09:30:00+00:00"
            amt = (self.rng.randint(200, 1500)) * 100
            ent = self.rng.choice(ENTITIES)
            r1 = self._next_row_id()
            r2 = self._next_row_id()
            self.ledger.append(LedgerRow(
                row_id=r1, timestamp=exp_ts, account=ACCOUNTS["EXPENSE"],
                debit_minor=amt, credit_minor=0, currency=self.base_currency, entity_id=ent, invoice_id=None, payment_id=None
            ))
            self.ledger.append(LedgerRow(
                row_id=r2, timestamp=exp_ts, account=ACCOUNTS["CASH"],
                debit_minor=0, credit_minor=amt, currency=self.base_currency, entity_id=ent, invoice_id=None, payment_id=None
            ))

        # Sort ledger by timestamp deterministically
        self.ledger.sort(key=lambda r: (r.timestamp, r.row_id))

        self.manifest = Manifest(
            schema_version="1.0.0",
            episode_id=self.episode_id,
            base_currency=self.base_currency,
            period_start=self.period_start,
            period_end=self.period_end,
            timezone=self.timezone,
            n_records=len(self.ledger),
            n_documents=len(self.invoices) + len(self.payments),
            rounding_rules=RoundingRules()
        )
