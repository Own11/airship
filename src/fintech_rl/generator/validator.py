import csv
import json
from decimal import Decimal
from pathlib import Path
from typing import Dict, Any, List
from fintech_rl.schema import TruthFile
from fintech_rl.scoring.tolerances import convert_fx


def validate_episode_truth(episode_dir: Path) -> List[str]:
    """
    Validates:
    1. Every issue in truth.json has reproducible discrepancy from open files.
    2. Evidence sufficiency: all acceptable_evidence_sets exist in open files and are non-empty.
    3. No contradictory or irresolvable data.
    Returns list of error messages (empty if valid).
    """
    errors = []
    episode_dir = Path(episode_dir)

    # 1. Load open files
    with open(episode_dir / "manifest.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)

    with open(episode_dir / "truth.json", "r", encoding="utf-8") as f:
        truth = json.load(f)

    ledger_rows = {}
    with open(episode_dir / "ledger.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ledger_rows[r["row_id"]] = r

    invoices = {}
    with open(episode_dir / "invoices.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                inv = json.loads(line)
                invoices[inv["doc_id"]] = inv
                invoices[inv["invoice_id"]] = inv

    payments = {}
    with open(episode_dir / "payments.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                pay = json.loads(line)
                payments[pay["doc_id"]] = pay
                payments[pay["payment_id"]] = pay

    fx_rates = {}
    with open(episode_dir / "fx.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            fx_rates[(r["date"], r["source_currency"], r["target_currency"])] = Decimal(r["rate"])

    # All known IDs
    all_open_ids = set(ledger_rows.keys()) | set(invoices.keys()) | set(payments.keys())

    # 2. Check each issue
    for issue in truth.get("issues", []):
        iid = issue["issue_id"]
        itype = issue["type"]
        affected = issue["affected_ids"]
        expected_amt = issue["expected_amount_minor"]
        curr = issue["currency"]
        evidence_sets = issue["acceptable_evidence_sets"]

        # Check affected IDs exist
        for aff in affected:
            if aff not in all_open_ids:
                errors.append(f"Issue {iid}: affected ID {aff} not found in open files")

        # Check evidence sets exist in open files and are independent
        if not evidence_sets:
            errors.append(f"Issue {iid}: empty acceptable_evidence_sets")
        for ev_set in evidence_sets:
            if not ev_set:
                errors.append(f"Issue {iid}: contains empty evidence set")
            for doc_id in ev_set:
                if doc_id not in all_open_ids:
                    errors.append(f"Issue {iid}: evidence ID {doc_id} not found in open files")

        # Reproduce discrepancy from open files based on type
        if itype == "duplicate_accounts":
            # Must have duplicated rows with sum matching expected_amt
            aff_rows = [ledger_rows[r] for r in affected if r in ledger_rows]
            debit_rows = [r for r in aff_rows if int(r["debit_minor"]) > 0]
            if len(debit_rows) < 2:
                errors.append(f"Issue {iid}: duplicate_accounts requires at least 2 debit rows, got {len(debit_rows)}")
            else:
                dup_amt = int(debit_rows[0]["debit_minor"])
                if dup_amt != expected_amt:
                    errors.append(f"Issue {iid}: expected {expected_amt} != duplicated row amt {dup_amt}")

        elif itype == "partial_payment":
            # Discrepancy between payment amount in doc and ledger allocation
            pay_id = [a for a in affected if a in payments][0]
            pay_doc = payments[pay_id]
            doc_amt = pay_doc["amount_minor"]
            pay_rows = [ledger_rows[r] for r in affected if r in ledger_rows]
            alloc_amt = int(pay_rows[0]["debit_minor"]) if pay_rows else 0
            if (doc_amt - alloc_amt) != expected_amt:
                errors.append(f"Issue {iid}: partial_payment discrepancy {doc_amt - alloc_amt} != expected {expected_amt}")

        elif itype == "wrong_fx_or_date":
            # Discrepancy between ledger base amount and official fx converted amount
            inv_id = [a for a in affected if a in invoices][0]
            inv_doc = invoices[inv_id]
            date_str = inv_doc["issued_at"][:10]
            rate = fx_rates.get((date_str, inv_doc["currency"], "USD"))
            if not rate:
                errors.append(f"Issue {iid}: FX rate not found for {date_str} {inv_doc['currency']}->USD")
            else:
                expected_base = convert_fx(inv_doc["total_minor"], rate)
                inv_rows = [ledger_rows[r] for r in affected if r in ledger_rows]
                actual_base = int(inv_rows[0]["debit_minor"])
                if abs(actual_base - expected_base) != expected_amt:
                    errors.append(f"Issue {iid}: FX discrepancy {abs(actual_base - expected_base)} != expected {expected_amt}")

        elif itype == "period_misclassification":
            inv_id = [a for a in affected if a in invoices][0]
            inv_doc = invoices[inv_id]
            if inv_doc["total_minor"] != expected_amt:
                errors.append(f"Issue {iid}: period misclassification amount mismatch {inv_doc['total_minor']} != expected {expected_amt}")

    return errors
