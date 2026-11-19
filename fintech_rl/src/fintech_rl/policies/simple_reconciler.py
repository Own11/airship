from typing import Dict, Any, List


class SimpleReconcilerPolicy:
    """
    A rule-based reconciler:
    1. Fetches ledger pages.
    2. Identifies exact duplicate rows sharing same (account, debit_minor, credit_minor, currency, invoice_id).
    3. Fetches supporting invoice document.
    4. Submits detected duplicates with evidence.
    """

    def __init__(self):
        self.state = "list_ledger"
        self.cursor = 0
        self.ledger_rows: List[Dict[str, Any]] = []
        self.detected_findings: List[Dict[str, Any]] = []
        self.pending_docs_to_fetch: List[str] = []
        self.fetched_docs: Dict[str, Dict[str, Any]] = {}
        self.current_doc_id: str = ""

    def reset(self):
        self.state = "list_ledger"
        self.cursor = 0
        self.ledger_rows.clear()
        self.detected_findings.clear()
        self.pending_docs_to_fetch.clear()
        self.fetched_docs.clear()
        self.current_doc_id = ""

    def act(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        if observation["remaining_steps"] <= 2 or self.state == "done":
            return {"type": "submit", "findings": self.detected_findings}

        action_res = observation.get("action_result") or {}

        if self.state == "list_ledger":
            if "records" in action_res and action_res.get("table") == "ledger":
                records = action_res["records"]
                self.ledger_rows.extend(records)
                next_cur = action_res.get("next_cursor")
                if next_cur is not None and next_cur < 150: # check first 150 records
                    self.cursor = next_cur
                    return {"type": "list_records", "table": "ledger", "cursor": self.cursor, "limit": 50}
                else:
                    self.state = "analyze"
            else:
                return {"type": "list_records", "table": "ledger", "cursor": 0, "limit": 50}

        if self.state == "analyze":
            # Check for duplicates on invoice rows
            # Group by invoice_id
            by_inv: Dict[str, List[Dict[str, Any]]] = {}
            for r in self.ledger_rows:
                inv_id = r.get("invoice_id")
                if inv_id and not r.get("payment_id"):
                    by_inv.setdefault(inv_id, []).append(r)

            for inv_id, rows in by_inv.items():
                debits = [r for r in rows if r["debit_minor"] > 0]
                credits = [r for r in rows if r["credit_minor"] > 0]
                if len(debits) >= 2 and len(credits) >= 2:
                    # Duplicate candidate
                    r1, r2 = debits[0], debits[1]
                    c1, c2 = credits[0], credits[1]
                    if r1["debit_minor"] == r2["debit_minor"] and r1["currency"] == r2["currency"]:
                        # Record candidate
                        self.detected_findings.append({
                            "type": "duplicate_accounts",
                            "affected_ids": [r1["row_id"], c1["row_id"], r2["row_id"], c2["row_id"], inv_id],
                            "claimed_amount_minor": r1["debit_minor"],
                            "currency": r1["currency"],
                            "evidence_ids": [r2["row_id"], c2["row_id"]], # Will add doc_id once fetched
                            "invoice_id": inv_id
                        })

            if self.detected_findings:
                self.state = "list_invoices"
                return {"type": "list_records", "table": "invoices", "cursor": 0, "limit": 50}
            else:
                self.state = "done"
                return {"type": "submit", "findings": []}

        if self.state == "list_invoices":
            if "records" in action_res and action_res.get("table") == "invoices":
                invoices = action_res["records"]
                inv_map = {inv["invoice_id"]: inv["doc_id"] for inv in invoices}
                for f in self.detected_findings:
                    inv_id = f.pop("invoice_id", None)
                    if inv_id in inv_map:
                        f["evidence_ids"].append(inv_map[inv_id])
                self.state = "done"
                return {"type": "submit", "findings": self.detected_findings}
            else:
                return {"type": "list_records", "table": "invoices", "cursor": 0, "limit": 50}

        return {"type": "submit", "findings": self.detected_findings}
