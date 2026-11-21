import csv
import json
import os
from pathlib import Path
from typing import Dict, Any
from fintech_rl.generator.company import SyntheticCompany
from fintech_rl.schema import TruthFile, ProvenanceFile


def render_episode_files(
    company: SyntheticCompany,
    truth_file: TruthFile,
    provenance_file: ProvenanceFile,
    output_dir: Path
) -> Dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. manifest.json
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(company.manifest.model_dump(), f, indent=2)

    # 2. policy.json
    policy_path = output_dir / "policy.json"
    with open(policy_path, "w", encoding="utf-8") as f:
        json.dump(company.policy.model_dump(), f, indent=2)

    # 3. fx.csv
    fx_path = output_dir / "fx.csv"
    with open(fx_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "source_currency", "target_currency", "rate"])
        for fx in company.fx_rates:
            writer.writerow([fx.date, fx.source_currency, fx.target_currency, str(fx.rate)])

    # 4. ledger.csv
    ledger_path = output_dir / "ledger.csv"
    with open(ledger_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "row_id", "timestamp", "account", "debit_minor", "credit_minor",
            "currency", "entity_id", "invoice_id", "payment_id"
        ])
        for r in company.ledger:
            writer.writerow([
                r.row_id, r.timestamp, r.account, r.debit_minor, r.credit_minor,
                r.currency, r.entity_id or "null", r.invoice_id or "null", r.payment_id or "null"
            ])

    # 5. invoices.jsonl
    inv_path = output_dir / "invoices.jsonl"
    with open(inv_path, "w", encoding="utf-8") as f:
        for inv in company.invoices:
            f.write(json.dumps(inv.model_dump()) + "\n")

    # 6. payments.jsonl
    pay_path = output_dir / "payments.jsonl"
    with open(pay_path, "w", encoding="utf-8") as f:
        for pay in company.payments:
            f.write(json.dumps(pay.model_dump()) + "\n")

    # 7. truth.json (evaluator only)
    truth_path = output_dir / "truth.json"
    with open(truth_path, "w", encoding="utf-8") as f:
        json.dump(truth_file.model_dump(), f, indent=2)

    # 8. provenance.json (evaluator only)
    prov_path = output_dir / "provenance.json"
    with open(prov_path, "w", encoding="utf-8") as f:
        json.dump(provenance_file.model_dump(), f, indent=2)

    return {
        "manifest": manifest_path,
        "policy": policy_path,
        "fx": fx_path,
        "ledger": ledger_path,
        "invoices": inv_path,
        "payments": pay_path,
        "truth": truth_path,
        "provenance": prov_path,
    }
