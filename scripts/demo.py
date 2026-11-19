import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fintech_rl.env.environment import FinancialAuditEnv
from fintech_rl.policies.oracle import OraclePolicy
from fintech_rl.policies.simple_reconciler import SimpleReconcilerPolicy


def print_section(title: str, text: str = ""):
    print("\n" + "=" * 65)
    print(f"  >>> {title}")
    print("=" * 65)
    if text:
        print(text)


def run_demo():
    root = Path(__file__).resolve().parent.parent
    episode_dir = root / "episodes" / "train" / "train_ep_03"
    if not episode_dir.exists():
        print(f"Error: episode directory not found at {episode_dir}")
        print("Please generate episodes first: python scripts/make_episodes.py")
        sys.exit(1)

    print("\n" + "#" * 65)
    print("      FINANCIAL STATEMENT AUDITOR RL ENVIRONMENT DEMO")
    print("#" * 65)

    env = FinancialAuditEnv(episode_dir=episode_dir, max_steps=10)
    obs, info = env.reset()

    manifest = obs["manifest_summary"]
    print_section(
        "STEP 0: EPISODE INITIALIZATION (RESET)",
        f"Episode ID: {info['episode_id']}\nStep Budget: {info['max_steps']}\n"
        f"Base Currency: {manifest['base_currency']}\n"
        f"Reporting Period: {manifest['period_start'][:10]} to {manifest['period_end'][:10]}\n"
        f"Total Ledger Records: {manifest['n_records']}"
    )

    # 1. Investigate ledger entries
    print_section("STEP 1: AGENT ACTION -> [list_records (ledger)]")
    obs, reward, term, trunc, _ = env.step({"type": "list_records", "table": "ledger", "cursor": 0, "limit": 50})
    res = obs.get("action_result") or {}
    print(f"Records received: {len(res.get('records', []))}, next_cursor={res.get('next_cursor')}")

    # 2. Investigate supporting invoices
    print_section("STEP 2: AGENT ACTION -> [list_records (invoices)]")
    obs, reward, term, trunc, _ = env.step({"type": "list_records", "table": "invoices", "cursor": 0, "limit": 20})
    res_inv = obs.get("action_result") or {}
    print(f"Invoices received: {len(res_inv.get('records', []))}, next_cursor={res_inv.get('next_cursor')}")

    # 3. Arithmetic verification on calculator
    print_section("STEP 3: AGENT ACTION -> [calculator]")
    calc_expr = "1440.00 * 100"
    obs, reward, term, trunc, _ = env.step({"type": "calculator", "expression": calc_expr})
    calc_res = obs.get("action_result") or {}
    print(f"Expression: '{calc_expr}' -> Verified minor units: {calc_res.get('result')}")

    # 4. Fetch specific primary document
    first_doc_id = res_inv.get("records", [{}])[0].get("doc_id", "DOC-INV-00001")
    print_section(f"STEP 4: AGENT ACTION -> [get_document ({first_doc_id})]")
    obs, reward, term, trunc, _ = env.step({"type": "get_document", "doc_id": first_doc_id})
    doc_res = obs.get("action_result") or {}
    print(f"Document verified: type={doc_res.get('doc_type')}, entity={doc_res.get('document', {}).get('entity_id')}")

    # 5. Submit findings using verified evidence
    oracle = OraclePolicy(episode_dir=episode_dir)
    submit_action = oracle.act(obs)
    findings = submit_action.get("findings", [])

    print_section(f"STEP 5: AGENT ACTION -> [submit ({len(findings)} findings)]")
    for idx, f in enumerate(findings, 1):
        print(f"  {idx}. Type: {f['type']}, Amount: {f['claimed_amount_minor']} {f['currency']}")
        print(f"     Affected IDs: {f['affected_ids']}")
        print(f"     Evidence IDs: {f['evidence_ids']}")

    obs, reward, terminated, truncated, step_info = env.step(submit_action)

    print_section("EVALUATOR SCORING & AUDIT VERDICT")
    metrics = step_info.get("eval_metrics", {})
    print(f"True Positives  (TP) : {metrics.get('tp')}")
    print(f"False Positives (FP) : {metrics.get('fp')}")
    print(f"False Negatives (FN) : {metrics.get('fn')}")
    print(f"Precision            : {metrics.get('precision', 0.0):.3f}")
    print(f"Recall               : {metrics.get('recall', 0.0):.3f}")
    print(f"F1-Score             : {metrics.get('f1', 0.0):.3f}")
    print(f"Terminal Reward      : {reward:.4f}")
    print(f"Status               : terminated={terminated}, truncated={truncated}")

    print("\n" + "#" * 65)
    print("      DEMONSTRATION EPISODE COMPLETED SUCCESSFULLY")
    print("#" * 65 + "\n")


if __name__ == "__main__":
    run_demo()
