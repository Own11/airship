import ast
from copy import deepcopy
from decimal import Decimal, DecimalException, localcontext
from typing import Any, Dict, List

from fintech_rl.identifiers import fx_record_id


SAFE_MATH_OPERATORS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.USub: lambda a: -a,
    ast.UAdd: lambda a: +a,
}


def safe_eval_expression(expr: str) -> Decimal:
    """Bounded arithmetic-only AST evaluation with exact decimal literals."""
    if not isinstance(expr, str) or not expr.strip() or len(expr) > 4096:
        raise ValueError("Calculator error: expression must contain 1 to 4096 characters")
    source = expr.strip()
    try:
        node = ast.parse(source, mode="eval")
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise ValueError("Calculator error: invalid arithmetic expression") from exc
    if sum(1 for _ in ast.walk(node)) > 256:
        raise ValueError("Calculator error: expression is too complex")

    def evaluate(part):
        if isinstance(part, ast.Expression):
            return evaluate(part.body)
        if isinstance(part, ast.Constant) and type(part.value) in (int, float):
            # ast.Constant.value is already a rounded binary float. Parse the token
            # itself, preserving all submitted decimal digits (including exponents).
            token = ast.get_source_segment(source, part)
            value = Decimal(token.replace("_", ""))
            if not value.is_finite() or (value and abs(value.adjusted()) > 1000):
                raise ValueError("Calculator error: number is outside the supported range")
            return value
        if isinstance(part, ast.UnaryOp) and type(part.op) in SAFE_MATH_OPERATORS:
            return SAFE_MATH_OPERATORS[type(part.op)](evaluate(part.operand))
        if isinstance(part, ast.BinOp) and type(part.op) in SAFE_MATH_OPERATORS:
            return SAFE_MATH_OPERATORS[type(part.op)](evaluate(part.left), evaluate(part.right))
        raise ValueError("Calculator error: Disallowed expression")

    try:
        with localcontext() as context:
            context.prec = 50
            context.Emax = 1000
            context.Emin = -1000
            value = evaluate(node)
            if not value.is_finite():
                raise ValueError("Calculator error: result must be finite")
            return value
    except (DecimalException, RecursionError) as exc:
        raise ValueError("Calculator error: invalid or excessive arithmetic") from exc


class ActionHandler:
    """Handles actions using detached public data, without filesystem capabilities."""

    def __init__(
        self,
        ledger: List[Dict[str, Any]],
        invoices: Dict[str, Dict[str, Any]],
        payments: Dict[str, Dict[str, Any]],
        fx_rates: List[Dict[str, Any]],
    ):
        self.ledger = deepcopy(ledger)
        self.invoices = deepcopy(invoices)
        self.payments = deepcopy(payments)
        self.fx_rates = []
        for source in fx_rates:
            quote = deepcopy(source)
            quote["id"] = fx_record_id(quote["date"], quote["source_currency"], quote["target_currency"])
            self.fx_rates.append(quote)
        self.ledger_by_id = {row["row_id"]: row for row in self.ledger}
        self.fx_by_id = {quote["id"]: quote for quote in self.fx_rates}
        if len(self.fx_by_id) != len(self.fx_rates):
            raise ValueError("FX natural keys must be unique")

    def list_records(self, table: str, cursor: int = 0, limit: int = 50) -> Dict[str, Any]:
        limit = max(1, min(limit, 50))
        cursor = max(0, cursor)
        if table == "ledger":
            data = self.ledger
        elif table == "fx":
            data = self.fx_rates
        elif table == "invoices":
            data = [
                {key: invoice[key] for key in (
                    "doc_id", "invoice_id", "entity_id", "issued_at", "currency", "total_minor", "document_type", "related_invoice_id"
                ) if key in invoice}
                for invoice in self.invoices.values()
            ]
        elif table == "payments":
            data = [
                {key: payment[key] for key in (
                    "doc_id", "payment_id", "timestamp", "currency", "amount_minor", "invoice_refs", "direction"
                ) if key in payment}
                for payment in self.payments.values()
            ]
        else:
            raise ValueError("Unknown table. Valid tables: ledger, fx, invoices, payments")
        total = len(data)
        slice_end = min(cursor + limit, total)
        return {
            "table": table,
            "cursor": cursor,
            "limit": limit,
            "total_records": total,
            "next_cursor": slice_end if slice_end < total else None,
            "records": deepcopy(data[cursor:slice_end]),
        }

    def get_record(self, table: str, id_value: str) -> Dict[str, Any]:
        if not isinstance(id_value, str):
            raise ValueError("Record id must be a string")
        if table == "ledger":
            record = self.ledger_by_id.get(id_value)
        elif table == "fx":
            record = self.fx_by_id.get(id_value)
        elif table == "invoices":
            record = next((invoice for invoice in self.invoices.values()
                           if id_value in (invoice["invoice_id"], invoice["doc_id"])), None)
        elif table == "payments":
            record = next((payment for payment in self.payments.values()
                           if id_value in (payment["payment_id"], payment["doc_id"])), None)
        else:
            raise ValueError("Unknown table. Valid tables: ledger, fx, invoices, payments")
        if record is None:
            raise KeyError("Record not found")
        return {"table": table, "record": deepcopy(record)}

    def get_document(self, doc_id: str) -> Dict[str, Any]:
        if not isinstance(doc_id, str):
            raise ValueError("Document id must be a string")
        if doc_id in self.invoices:
            return {"doc_type": "invoice", "document": deepcopy(self.invoices[doc_id])}
        if doc_id in self.payments:
            return {"doc_type": "payment", "document": deepcopy(self.payments[doc_id])}
        raise KeyError("Document not found")

    def calculator(self, expression: str) -> Dict[str, Any]:
        return {"expression": expression, "result": str(safe_eval_expression(expression))}
