import ast
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, List, Optional, Union
from fintech_rl.schema import FindingClaim


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
    """Safely evaluates an arithmetic expression using Decimal arithmetic."""
    node = ast.parse(expr.strip(), mode="eval")

    def _eval(n):
        if isinstance(n, ast.Expression):
            return _eval(n.body)
        elif isinstance(n, ast.Constant):
            if isinstance(n.value, (int, float, str)):
                return Decimal(str(n.value))
            raise ValueError(f"Unsupported constant: {n.value}")
        elif isinstance(n, ast.UnaryOp):
            op_type = type(n.op)
            if op_type in SAFE_MATH_OPERATORS:
                return SAFE_MATH_OPERATORS[op_type](_eval(n.operand))
            raise ValueError(f"Unsupported unary operator: {op_type}")
        elif isinstance(n, ast.BinOp):
            op_type = type(n.op)
            if op_type in SAFE_MATH_OPERATORS:
                return SAFE_MATH_OPERATORS[op_type](_eval(n.left), _eval(n.right))
            raise ValueError(f"Unsupported binary operator: {op_type}")
        else:
            raise ValueError(f"Disallowed expression node: {type(n)}")

    return _eval(node)


class ActionHandler:
    """Handles actions inside the environment state without shell or filesystem access."""

    def __init__(
        self,
        ledger: List[Dict[str, Any]],
        invoices: Dict[str, Dict[str, Any]],
        payments: Dict[str, Dict[str, Any]],
        fx_rates: List[Dict[str, Any]]
    ):
        self.ledger = ledger
        self.invoices = invoices
        self.payments = payments
        self.fx_rates = fx_rates

        # Index ledger rows by row_id
        self.ledger_by_id = {r["row_id"]: r for r in self.ledger}

    def list_records(self, table: str, cursor: int = 0, limit: int = 50) -> Dict[str, Any]:
        limit = max(1, min(limit, 50))  # Max 50 per page
        cursor = max(0, cursor)

        if table == "ledger":
            data = self.ledger
        elif table == "fx":
            data = self.fx_rates
        elif table == "invoices":
            # Return list of summaries
            data = [
                {
                    "doc_id": inv["doc_id"],
                    "invoice_id": inv["invoice_id"],
                    "entity_id": inv["entity_id"],
                    "issued_at": inv["issued_at"],
                    "currency": inv["currency"],
                    "total_minor": inv["total_minor"]
                }
                for inv in self.invoices.values()
            ]
        elif table == "payments":
            data = [
                {
                    "doc_id": p["doc_id"],
                    "payment_id": p["payment_id"],
                    "timestamp": p["timestamp"],
                    "currency": p["currency"],
                    "amount_minor": p["amount_minor"],
                    "invoice_refs": p["invoice_refs"]
                }
                for p in self.payments.values()
            ]
        else:
            raise ValueError(f"Unknown table '{table}'. Valid tables: ['ledger', 'fx', 'invoices', 'payments']")

        total = len(data)
        slice_end = min(cursor + limit, total)
        records = data[cursor:slice_end]
        next_cursor = slice_end if slice_end < total else None

        return {
            "table": table,
            "cursor": cursor,
            "limit": limit,
            "total_records": total,
            "next_cursor": next_cursor,
            "records": records
        }

    def get_record(self, table: str, id_value: str) -> Dict[str, Any]:
        if table == "ledger":
            if id_value in self.ledger_by_id:
                return {"table": "ledger", "record": self.ledger_by_id[id_value]}
            raise KeyError(f"Ledger row with id '{id_value}' not found")
        elif table == "invoices":
            for inv in self.invoices.values():
                if inv["invoice_id"] == id_value or inv["doc_id"] == id_value:
                    return {"table": "invoices", "record": inv}
            raise KeyError(f"Invoice with id '{id_value}' not found")
        elif table == "payments":
            for p in self.payments.values():
                if p["payment_id"] == id_value or p["doc_id"] == id_value:
                    return {"table": "payments", "record": p}
            raise KeyError(f"Payment with id '{id_value}' not found")
        else:
            raise ValueError(f"Unknown table '{table}' for get_record. Valid: ['ledger', 'invoices', 'payments']")

    def get_document(self, doc_id: str) -> Dict[str, Any]:
        if doc_id in self.invoices:
            return {"doc_type": "invoice", "document": self.invoices[doc_id]}
        if doc_id in self.payments:
            return {"doc_type": "payment", "document": self.payments[doc_id]}
        raise KeyError(f"Document with doc_id '{doc_id}' not found")

    def calculator(self, expression: str) -> Dict[str, Any]:
        try:
            val = safe_eval_expression(expression)
            return {"expression": expression, "result": str(val)}
        except Exception as e:
            raise ValueError(f"Calculator error: {str(e)}")
