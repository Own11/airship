from decimal import Decimal
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class RoundingRules(BaseModel):
    method: Literal["ROUND_HALF_UP", "ROUND_HALF_EVEN", "ROUND_FLOOR", "ROUND_CEILING"] = "ROUND_HALF_UP"
    minor_unit_digits: int = 2


class Manifest(BaseModel):
    schema_version: str = "1.0.0"
    episode_id: str
    base_currency: str
    period_start: str  # ISO-8601 with tz
    period_end: str    # ISO-8601 with tz
    timezone: str
    n_records: int
    n_documents: int
    rounding_rules: RoundingRules = Field(default_factory=RoundingRules)


class LedgerRow(BaseModel):
    row_id: str
    timestamp: str     # ISO-8601 with offset
    account: str
    debit_minor: int = Field(ge=0)
    credit_minor: int = Field(ge=0)
    currency: str
    entity_id: Optional[str] = None
    invoice_id: Optional[str] = None
    payment_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_one_sided(self):
        if (self.debit_minor > 0 and self.credit_minor > 0) or (self.debit_minor == 0 and self.credit_minor == 0):
            raise ValueError(f"Ledger row {self.row_id} must have exactly one of debit_minor or credit_minor > 0")
        return self


class InvoiceLineItem(BaseModel):
    item_id: str
    description: str
    quantity: int = Field(gt=0)
    unit_price_minor: int = Field(ge=0)
    total_minor: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_line_total(self):
        if self.quantity * self.unit_price_minor != self.total_minor:
            raise ValueError(f"Line item {self.item_id} total_minor != quantity * unit_price_minor")
        return self


class InvoiceDoc(BaseModel):
    doc_id: str
    invoice_id: str
    entity_id: str
    issued_at: str   # ISO-8601 with tz
    due_at: str      # ISO-8601 with tz
    currency: str
    total_minor: int = Field(ge=0)
    line_items: List[InvoiceLineItem] = Field(default_factory=list)
    document_type: Literal["invoice", "credit_note"] = "invoice"
    related_invoice_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_sum(self):
        if self.document_type == "credit_note" and (
            not self.related_invoice_id or self.related_invoice_id == self.invoice_id
        ):
            raise ValueError("A credit note must reference its original invoice")
        if self.line_items:
            s = sum(item.total_minor for item in self.line_items)
            if s != self.total_minor:
                raise ValueError(f"Invoice {self.invoice_id} sum of line items ({s}) != total_minor ({self.total_minor})")
        return self


class PaymentDoc(BaseModel):
    doc_id: str
    payment_id: str
    timestamp: str   # ISO-8601 with tz
    currency: str
    amount_minor: int = Field(gt=0)
    invoice_refs: List[str] = Field(default_factory=list)
    direction: Literal["receipt", "refund"] = "receipt"


class FXRateRow(BaseModel):
    date: str  # YYYY-MM-DD
    source_currency: str
    target_currency: str
    rate: Decimal

    @field_validator("rate", mode="before")
    @classmethod
    def parse_rate_decimal(cls, v):
        if isinstance(v, (str, int, float, Decimal)):
            return Decimal(str(v))
        raise ValueError(f"Invalid decimal rate: {v}")


class AccountingPolicy(BaseModel):
    fx_rate_date_rule: Literal["transaction_date", "document_date", "month_end"] = "transaction_date"
    period_boundary_rule: Literal["transaction_timestamp", "due_date", "settlement_date"] = "transaction_timestamp"
    rounding: Literal["nearest", "truncate"] = "nearest"


ERROR_TYPE_ALIASES = {
    "duplicate_accounts": "duplicate_accounts",
    "duplicate_account": "duplicate_accounts",
    "duplicate_invoices": "duplicate_accounts",
    "duplicate_invoice": "duplicate_accounts",
    "duplicate_entries": "duplicate_accounts",
    "duplicate_entry": "duplicate_accounts",
    "duplicate": "duplicate_accounts",
    "partial_payment": "partial_payment",
    "partial_payments": "partial_payment",
    "missed_payment": "partial_payment",
    "incomplete_payment": "partial_payment",
    "unallocated_payment": "partial_payment",
    "wrong_fx_or_date": "wrong_fx_or_date",
    "wrong_fx": "wrong_fx_or_date",
    "wrong_date": "wrong_fx_or_date",
    "fx_error": "wrong_fx_or_date",
    "fx_conversion_error": "wrong_fx_or_date",
    "period_misclassification": "period_misclassification",
    "period_error": "period_misclassification",
    "cutoff_error": "period_misclassification",
    "period_cutoff": "period_misclassification",
}


def normalize_error_type(t: str) -> str:
    cleaned = str(t).strip().lower().replace("-", "_").replace(" ", "_")
    return ERROR_TYPE_ALIASES.get(cleaned, cleaned)


class FindingClaim(BaseModel):
    type: Literal[
        "duplicate_accounts",
        "partial_payment",
        "wrong_fx_or_date",
        "period_misclassification"
    ]
    affected_ids: List[str]
    claimed_amount_minor: int = Field(ge=0)
    currency: str
    evidence_ids: List[str]
    explanation: str = Field(default="", max_length=1000)

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type_str(cls, v):
        if isinstance(v, str):
            return normalize_error_type(v)
        return v

    @model_validator(mode="after")
    def validate_unique_and_sorted(self):
        if not self.affected_ids:
            raise ValueError("Finding must have non-empty affected_ids")
        if not self.evidence_ids:
            raise ValueError("Finding must have non-empty evidence_ids")
        if len(self.evidence_ids) > 10:
            raise ValueError(f"Exceeded max 10 evidence IDs (got {len(self.evidence_ids)})")
        return self


class FindingsReport(BaseModel):
    episode_id: str
    findings: List[FindingClaim] = Field(default_factory=list, max_length=30)


class TruthIssue(BaseModel):
    issue_id: str
    type: Literal[
        "duplicate_accounts",
        "partial_payment",
        "wrong_fx_or_date",
        "period_misclassification"
    ]
    affected_ids: List[str]
    expected_amount_minor: int = Field(ge=0)
    currency: str
    acceptable_evidence_sets: List[List[str]]  # Any one of these sets is sufficient evidence

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type_str(cls, v):
        if isinstance(v, str):
            return normalize_error_type(v)
        return v

    @model_validator(mode="after")
    def validate_evidence_sets(self):
        if not self.affected_ids:
            raise ValueError("Truth issue must have non-empty affected_ids")
        if not self.acceptable_evidence_sets:
            raise ValueError(f"Truth issue {self.issue_id} must have at least one acceptable evidence set")
        if any(not evidence or len(evidence) > 10 for evidence in self.acceptable_evidence_sets):
            raise ValueError("Each truth evidence set must contain between one and ten IDs")
        return self


class TruthFile(BaseModel):
    episode_id: str
    issues: List[TruthIssue] = Field(default_factory=list)


class ProvenanceChange(BaseModel):
    issue_id: str
    type: str
    affected_ids: List[str]
    expected_amount_minor: int
    currency: str
    acceptable_evidence_sets: List[List[str]]
    description: str
    before_state: Dict[str, Any] = Field(default_factory=dict)
    after_state: Dict[str, Any] = Field(default_factory=dict)


class ProvenanceFile(BaseModel):
    episode_id: str
    seed: int
    created_at: str
    changes: List[ProvenanceChange] = Field(default_factory=list)
    generator_version: str = "1.0.0"
    generation_config: Dict[str, Any] = Field(default_factory=dict)
    error_types: List[str] = Field(default_factory=list)
