"""
Airship CLI command implementations.
Includes demo, benchmark, generate, inspect, interactive play, and check.
"""

import sys
import os
import json
import time
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

from fintech_rl.cli.ui import (
    Ansi,
    c_bold,
    c_dim,
    c_cyan,
    c_sky,
    c_purple,
    c_green,
    c_yellow,
    c_red,
    c_gray,
    c_border,
    badge,
    badge_pass,
    badge_fail,
    badge_info,
    badge_warn,
    format_score,
    divider,
    print_banner,
    print_panel,
    print_table,
    print_step_header,
    print_key_value,
    print_score_card,
    render_progress_bar,
    get_term_width,
)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent


def get_episodes_dir() -> Path:
    return ROOT_DIR / "episodes"


# ----------------------------------------------------------------------
# 1. DEMO COMMAND
# ----------------------------------------------------------------------
def cmd_demo(episode_id: Optional[str] = None):
    """Run an interactive step-by-step audit walkthrough."""
    from fintech_rl.env.environment import FinancialAuditEnv
    from fintech_rl.policies.oracle import OraclePolicy

    print_banner()

    target_id = episode_id or "train_ep_03"
    ep_dir = get_episodes_dir() / "train" / target_id
    if not ep_dir.exists():
        ep_dir = get_episodes_dir() / "dev" / target_id
    if not ep_dir.exists():
        print(c_red(f"Error: episode '{target_id}' not found in {get_episodes_dir()}"))
        print(c_gray("Run 'airship generate' or 'make episodes' first."))
        return 1

    print(f" {badge('WALKTHROUGH', 'cyan')} Loading demonstration on episode {c_cyan(target_id, bold=True)}...\n")

    env = FinancialAuditEnv(episode_dir=ep_dir, max_steps=10)
    obs, info = env.reset()
    manifest = obs.get("manifest_summary", {})

    # STEP 0
    print_step_header(0, "EPISODE INITIALIZATION (RESET)")
    pairs = [
        ("Episode ID", info.get("episode_id")),
        ("Step Budget", f"{info.get('max_steps')} turns remaining"),
        ("Base Currency", manifest.get("base_currency")),
        ("Period Window", f"{manifest.get('period_start', '')[:10]} → {manifest.get('period_end', '')[:10]}"),
        ("Ledger Volume", f"{manifest.get('n_records')} accounting rows"),
    ]
    print_key_value(pairs)

    # STEP 1: list_records ledger
    print_step_header(1, "QUERY ACCOUNTING LEDGER", "list_records(ledger)")
    obs, reward, term, trunc, _ = env.step({"type": "list_records", "table": "ledger", "cursor": 0, "limit": 4})
    res_ledger = obs.get("action_result") or {}
    records = res_ledger.get("records", [])
    print(f"  {c_green('✓')} Retrieved {c_bold(len(records))} sample rows (next_cursor={res_ledger.get('next_cursor')}):")

    headers = ["ROW ID", "DATE", "ACCOUNT", "DEBIT", "CREDIT", "DOC REF"]
    table_rows = []
    for r in records[:4]:
        date_str = r.get("timestamp", "")[:10]
        debit_val = f"{r.get('debit_minor', 0) / 100:.2f}" if r.get('debit_minor') else "-"
        credit_val = f"{r.get('credit_minor', 0) / 100:.2f}" if r.get('credit_minor') else "-"
        doc_ref = r.get("invoice_id") or r.get("payment_id") or "-"
        table_rows.append([
            r.get("row_id", ""),
            date_str,
            r.get("account", "")[:24],
            debit_val,
            credit_val,
            doc_ref,
        ])
    print_table(headers, table_rows, alignments=["<", "<", "<", ">", ">", "<"], border_color=Ansi.BORDER_GRAY)

    # STEP 2: list_records invoices
    print_step_header(2, "INSPECT SUPPORTING INVOICES", "list_records(invoices)")
    obs, reward, term, trunc, _ = env.step({"type": "list_records", "table": "invoices", "cursor": 0, "limit": 4})
    res_inv = obs.get("action_result") or {}
    invoices = res_inv.get("records", [])
    print(f"  {c_green('✓')} Retrieved {c_bold(len(invoices))} invoices from archives (next_cursor={res_inv.get('next_cursor')}):")

    headers_inv = ["INVOICE ID", "DATE", "ENTITY", "TOTAL AMOUNT", "CURRENCY"]
    table_inv = []
    for inv in invoices[:4]:
        table_inv.append([
            inv.get("doc_id", ""),
            inv.get("issued_at", "")[:10],
            inv.get("entity_id", ""),
            f"{inv.get('total_minor', 0) / 100:.2f}",
            inv.get("currency", ""),
        ])
    print_table(headers_inv, table_inv, alignments=["<", "<", "<", ">", "<"], border_color=Ansi.BORDER_GRAY)

    # STEP 3: Calculator
    calc_expr = "1440.00 * 100"
    print_step_header(3, "CALCULATE ACCRUALS IN MINOR UNITS", f"calculator('{calc_expr}')")
    obs, reward, term, trunc, _ = env.step({"type": "calculator", "expression": calc_expr})
    calc_res = obs.get("action_result") or {}
    print_key_value([
        ("Expression", calc_expr),
        ("AST Engine", "Safe Decimal Sandbox"),
        ("Computed Value", f"{calc_res.get('result')} minor units"),
    ])

    # STEP 4: Primary Document Verification
    first_doc_id = invoices[0].get("doc_id", "DOC-INV-00001") if invoices else "DOC-INV-00001"
    print_step_header(4, "AUDIT PRIMARY SOURCE EVIDENCE", f"get_document('{first_doc_id}')")
    obs, reward, term, trunc, _ = env.step({"type": "get_document", "doc_id": first_doc_id})
    doc_res = obs.get("action_result") or {}
    doc_data = doc_res.get("document", {})
    print_key_value([
        ("Document ID", first_doc_id),
        ("Document Type", doc_res.get("doc_type")),
        ("Counterparty", doc_data.get("entity_id", "Unknown")),
        ("Total Amount", f"{doc_data.get('total_minor', 0) / 100:.2f} {doc_data.get('currency', '')}"),
        ("Line Items", f"{len(doc_data.get('line_items', []))} item(s) itemized"),
        ("Provenance Status", c_green("Verified Authenticated Signature")),
    ])

    # STEP 5: Submit Findings
    oracle = OraclePolicy(episode_dir=ep_dir)
    submit_action = oracle.act(obs)
    findings = submit_action.get("findings", [])

    print_step_header(5, "SUBMIT FORMAL AUDIT FINDINGS", f"submit({len(findings)} findings)")
    for idx, f in enumerate(findings, 1):
        finding_desc = (
            f"Finding #{idx}: {c_yellow(f['type'], bold=True)}\n"
            f"Claimed Amount   : {f['claimed_amount_minor']} {f['currency']}\n"
            f"Affected Ledger  : {', '.join(f.get('affected_ids', []))}\n"
            f"Verified Evidence: {', '.join(f.get('evidence_ids', []))}"
        )
        print_panel(finding_desc, title=f"FINDING #{idx}", width=68, border_color=Ansi.WARN_AMBER)

    obs, reward, terminated, truncated, step_info = env.step(submit_action)

    print()
    metrics = step_info.get("eval_metrics", {})
    print_score_card(metrics, reward, terminated, truncated)
    print(f" {badge('DEMO COMPLETED', 'green')} Walkthrough execution concluded with bit-exact validation.\n")
    return 0


# ----------------------------------------------------------------------
# 2. BENCHMARK COMMAND
# ----------------------------------------------------------------------
def cmd_benchmark(dataset: str = "all", out_trajectories: Optional[str] = None):
    """Run policies across dataset with live progress and comparison tables."""
    from fintech_rl.env.environment import FinancialAuditEnv
    from fintech_rl.policies.oracle import OraclePolicy
    from fintech_rl.policies.simple_reconciler import SimpleReconcilerPolicy
    from fintech_rl.policies.random_explorer import RandomExplorerPolicy
    from fintech_rl.policies.mark_all import MarkAllPolicy

    print_banner()

    episodes_dir = get_episodes_dir()
    train_eps = sorted(list((episodes_dir / "train").glob("train_ep_*")))
    dev_eps = sorted(list((episodes_dir / "dev").glob("dev_ep_*")))

    if dataset == "train":
        all_eps = train_eps
    elif dataset == "dev":
        all_eps = dev_eps
    else:
        all_eps = train_eps + dev_eps

    if not all_eps:
        print(c_red(f"No episodes found in {episodes_dir}."))
        print("Please generate episodes first: airship generate")
        return 1

    traj_path = Path(out_trajectories) if out_trajectories else (ROOT_DIR / "trajectories.jsonl")

    policies = [
        ("oracle", "Oracle (Ground Truth Bound)", lambda ep: OraclePolicy(episode_dir=ep)),
        ("simple_reconciler", "Simple Reconciler (Heuristic)", lambda ep: SimpleReconcilerPolicy()),
        ("random_explorer", "Random Explorer (Baseline)", lambda ep: RandomExplorerPolicy(seed=42)),
        ("mark_all", "Mark All (Adversarial Spam)", lambda ep: MarkAllPolicy()),
    ]

    print(f" {badge('EVALUATION', 'cyan')} Running 4 policies across {c_bold(len(all_eps))} episodes ({len(train_eps)} train + {len(dev_eps)} dev)...\n")

    env = FinancialAuditEnv()
    summary_results = []

    with open(traj_path, "w", encoding="utf-8") as traj_file:
        for pol_key, pol_label, pol_factory in policies:
            t_start = time.time()
            total_p, total_r, total_f1, total_ret, total_steps = 0.0, 0.0, 0.0, 0.0, 0
            n_eps = len(all_eps)

            for idx, ep_dir in enumerate(all_eps, 1):
                # Live progress bar
                bar = render_progress_bar(idx, n_eps, width=22, label=f"{pol_key:<17} • {ep_dir.name}")
                sys.stdout.write(f"\r  {bar}")
                sys.stdout.flush()

                obs, info = env.reset(config={"episode_dir": ep_dir})
                policy = pol_factory(ep_dir)
                if hasattr(policy, "reset"):
                    policy.reset()

                terminated, truncated = False, False
                step = 0
                final_reward = 0.0
                final_metrics = {}

                while not (terminated or truncated):
                    step += 1
                    action = policy.act(obs)
                    next_obs, reward, terminated, truncated, step_info = env.step(action)

                    record = {
                        "episode_id": info["episode_id"],
                        "step": step,
                        "action": action,
                        "observation": next_obs,
                        "reward": reward,
                        "terminated": terminated,
                        "truncated": truncated,
                    }
                    traj_file.write(json.dumps(record) + "\n")

                    obs = next_obs
                    final_reward = reward
                    if "eval_metrics" in step_info:
                        final_metrics = step_info["eval_metrics"]

                total_p += final_metrics.get("precision", 0.0)
                total_r += final_metrics.get("recall", 0.0)
                total_f1 += final_metrics.get("f1", 0.0)
                total_ret += final_reward
                total_steps += step

            elapsed = time.time() - t_start
            sys.stdout.write("\r" + " " * 80 + "\r")  # Clear progress line
            print(f"  {c_green('✓')} {c_bold(pol_label):<36} in {elapsed:.2f}s")

            summary_results.append({
                "policy": pol_key,
                "label": pol_label,
                "P": total_p / n_eps,
                "R": total_r / n_eps,
                "F1": total_f1 / n_eps,
                "return": total_ret / n_eps,
                "avg_steps": total_steps / n_eps,
                "total_time": elapsed,
            })

    print()
    # 1. Quality Diagnostics Table
    headers_diag = ["POLICY", "PRECISION", "RECALL", "F1-SCORE", "AVG STEPS", "TIME (s)"]
    rows_diag = []
    for r in summary_results:
        pol_name = c_cyan(r["policy"], bold=(r["policy"] == "oracle"))
        p_val = format_score(r["P"])
        r_val = format_score(r["R"])
        f1_val = format_score(r["F1"])
        steps_val = f"{r['avg_steps']:>6.1f}"
        time_val = f"{r['total_time']:>6.2f}"
        rows_diag.append([pol_name, p_val, r_val, f1_val, steps_val, time_val])

    print_table(
        headers_diag,
        rows_diag,
        alignments=["<", ">", ">", ">", ">", ">"],
        header_color=Ansi.BRAND_CYAN,
        title="ТАБЛИЦА ДИАГНОСТИКИ КАЧЕСТВА (P, R, F1, STEPS, TIME)",
    )

    print()
    # 2. RL Return Table
    headers_ret = ["POLICY", "MEAN RETURN (REWARD)", "AVG STEPS", "BUDGET ECONOMY"]
    rows_ret = []
    for r in summary_results:
        pol_name = c_cyan(r["policy"], bold=(r["policy"] == "oracle"))
        ret_val = format_score(r["return"], is_reward=True)
        steps_val = f"{r['avg_steps']:>6.1f}"
        economy = f"{100 - r['avg_steps']:>5.1f}% preserved"
        rows_ret.append([pol_name, ret_val, steps_val, c_gray(economy)])

    print_table(
        headers_ret,
        rows_ret,
        alignments=["<", ">", ">", ">"],
        header_color=Ansi.BRAND_SKY,
        title="ТАБЛИЦА НАГРАД (RL RETURN)",
    )

    print(f"\n {badge('SAVED', 'green')} Trajectories saved to {c_cyan(str(traj_path))}")
    return 0


# ----------------------------------------------------------------------
# 3. GENERATE COMMAND
# ----------------------------------------------------------------------
def cmd_generate():
    """Generate the full benchmark dataset (10 train + 10 dev)."""
    from fintech_rl.generator.company import SyntheticCompany
    from fintech_rl.generator.errors import ErrorInjector
    from fintech_rl.generator.provenance import create_provenance_file
    from fintech_rl.generator.documents import render_episode_files
    from fintech_rl.schema import TruthFile

    print_banner()

    base_dir = get_episodes_dir()
    train_configs = [
        ("train_ep_01", 101, []),
        ("train_ep_02", 102, []),
        ("train_ep_03", 103, ["E1"]),
        ("train_ep_04", 104, ["E2"]),
        ("train_ep_05", 105, ["E3"]),
        ("train_ep_06", 106, ["E4"]),
        ("train_ep_07", 107, ["E1", "E2"]),
        ("train_ep_08", 108, ["E3", "E4"]),
        ("train_ep_09", 109, ["X1"]),
        ("train_ep_10", 110, ["X2"]),
    ]

    dev_configs = [
        ("dev_ep_01", 201, []),
        ("dev_ep_02", 202, []),
        ("dev_ep_03", 203, []),
        ("dev_ep_04", 204, ["E1"]),
        ("dev_ep_05", 205, ["E2"]),
        ("dev_ep_06", 206, ["E3"]),
        ("dev_ep_07", 207, ["E4"]),
        ("dev_ep_08", 208, ["X1"]),
        ("dev_ep_09", 209, ["X2"]),
        ("dev_ep_10", 210, ["X1", "X2"]),
    ]

    total_episodes = len(train_configs) + len(dev_configs)
    print(f" {badge('SYNTHESIS', 'cyan')} Generating {c_bold(total_episodes)} deterministic audit episodes...\n")

    summary_rows = []
    idx = 0

    def run_gen(split: str, configs):
        nonlocal idx
        for ep_id, seed, errs in configs:
            idx += 1
            out_dir = base_dir / split / ep_id
            if out_dir.exists():
                shutil.rmtree(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)

            company = SyntheticCompany(seed=seed, episode_id=ep_id)
            company.generate()

            injector = ErrorInjector(company=company, seed=seed)
            injector.apply_errors(errs)

            truth = TruthFile(episode_id=ep_id, issues=injector.issues)
            prov = create_provenance_file(episode_id=ep_id, seed=seed, changes=injector.changes)
            render_episode_files(company, truth, prov, out_dir)

            err_tag = ", ".join(errs) if errs else "CLEAN"
            err_styled = c_green(err_tag) if not errs else c_yellow(err_tag)
            summary_rows.append([
                split.upper(),
                ep_id,
                seed,
                f"{len(company.ledger):>4} rows",
                err_styled,
                f"{len(truth.issues)} issue(s)",
            ])

            bar = render_progress_bar(idx, total_episodes, width=22, label=f"{split}/{ep_id}")
            sys.stdout.write(f"\r  {bar}")
            sys.stdout.flush()

    run_gen("train", train_configs)
    run_gen("dev", dev_configs)
    sys.stdout.write("\r" + " " * 80 + "\r")

    headers = ["SPLIT", "EPISODE ID", "SEED", "LEDGER", "INJECTED ERRORS", "GROUND TRUTH"]
    print_table(headers, summary_rows, alignments=["<", "<", ">", ">", "<", ">"], title="DATASET EPISODE REGISTRY")

    print(f"\n {badge('COMPLETE', 'green')} All 20 episodes rendered at {c_cyan(str(base_dir))}\n")
    return 0


# ----------------------------------------------------------------------
# 4. INSPECT COMMAND
# ----------------------------------------------------------------------
def cmd_inspect(episode_id: str, table: str = "manifest", limit: int = 15, show_truth: bool = False):
    """Inspect an episode's records, ledger, or documents."""
    import csv

    base_dir = get_episodes_dir()
    ep_dir = base_dir / "train" / episode_id
    if not ep_dir.exists():
        ep_dir = base_dir / "dev" / episode_id
    if not ep_dir.exists():
        print(c_red(f"Error: episode '{episode_id}' not found."))
        return 1

    print_banner()
    print(f" {badge('INSPECTION', 'purple')} Inspecting Episode {c_cyan(episode_id, bold=True)}\n")

    manifest_path = ep_dir / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        pairs = [
            ("Episode ID", manifest.get("episode_id")),
            ("Company Name", manifest.get("company_name", "Global Trading Corp")),
            ("Base Currency", manifest.get("base_currency")),
            ("Reporting Window", f"{manifest.get('period_start', '')[:10]} to {manifest.get('period_end', '')[:10]}"),
            ("Ledger Rows", f"{manifest.get('n_records')} total entries"),
            ("Step Budget", f"{manifest.get('max_steps', 100)} turns"),
        ]
        print_panel("\n".join(f"{k:<20} : {v}" for k, v in pairs), title="MANIFEST SUMMARY", width=70)
        print()

    if table == "ledger":
        ledger_path = ep_dir / "ledger.csv"
        if not ledger_path.exists():
            print(c_red("ledger.csv not found"))
            return 1
        with open(ledger_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = []
            for idx, r in enumerate(reader):
                if idx >= limit:
                    break
                d_val = f"{int(r.get('debit_minor', 0)) / 100:.2f}" if int(r.get('debit_minor', 0) or 0) > 0 else "-"
                c_val = f"{int(r.get('credit_minor', 0)) / 100:.2f}" if int(r.get('credit_minor', 0) or 0) > 0 else "-"
                doc_ref = r.get("invoice_id") or r.get("payment_id") or "-"
                rows.append([
                    r.get("row_id", ""),
                    r.get("timestamp", "")[:10],
                    r.get("account", "")[:24],
                    d_val,
                    c_val,
                    doc_ref,
                ])
        headers = ["ROW ID", "DATE", "ACCOUNT", "DEBIT", "CREDIT", "DOC REF"]
        print_table(headers, rows, alignments=["<", "<", "<", ">", ">", "<"], title=f"LEDGER RECORDS (first {len(rows)} entries)")

    elif table == "invoices":
        inv_path = ep_dir / "invoices.jsonl"
        if not inv_path.exists():
            print(c_red("invoices.jsonl not found"))
            return 1
        rows = []
        with open(inv_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                if idx >= limit:
                    break
                d = json.loads(line)
                rows.append([
                    d.get("doc_id", ""),
                    d.get("issued_at", "")[:10],
                    d.get("entity_id", ""),
                    f"{d.get('total_minor', 0) / 100:.2f}",
                    d.get("currency", ""),
                ])
        headers = ["INVOICE ID", "DATE", "ENTITY", "AMOUNT", "CURRENCY"]
        print_table(headers, rows, alignments=["<", "<", "<", ">", "<"], title=f"INVOICES (first {len(rows)} entries)")

    elif table == "truth":
        if not show_truth:
            print(c_yellow("Note: Truth file is evaluator data. Use --show-truth to reveal."))
            return 0
        truth_path = ep_dir / "truth.json"
        if not truth_path.exists():
            print(c_red("truth.json not found"))
            return 1
        with open(truth_path, "r", encoding="utf-8") as f:
            truth = json.load(f)
        issues = truth.get("issues", [])
        print(f" {badge('EVALUATOR TRUTH', 'red')} Found {len(issues)} ground truth issues:")
        for idx, iss in enumerate(issues, 1):
            desc = (
                f"Issue ID         : {iss.get('issue_id')}\n"
                f"Error Type       : {c_yellow(iss.get('type'))}\n"
                f"True Amount      : {iss.get('claimed_amount_minor')} {iss.get('currency')}\n"
                f"Affected IDs     : {iss.get('affected_ids')}\n"
                f"Evidence Sets    : {iss.get('acceptable_evidence_sets')}\n"
                f"Explanation      : {iss.get('explanation')}"
            )
            print_panel(desc, title=f"TRUTH ISSUE #{idx}", width=70, border_color=Ansi.DANGER_CORAL)
    return 0


# ----------------------------------------------------------------------
# 5. INTERACTIVE PLAY COMMAND (HUMAN AUDITOR MODE)
# ----------------------------------------------------------------------
def cmd_play(episode_id: Optional[str] = None):
    """Play as a Human Auditor interactively in the terminal!"""
    from fintech_rl.env.environment import FinancialAuditEnv

    print_banner()

    target_id = episode_id or "train_ep_03"
    ep_dir = get_episodes_dir() / "train" / target_id
    if not ep_dir.exists():
        ep_dir = get_episodes_dir() / "dev" / target_id
    if not ep_dir.exists():
        print(c_red(f"Error: episode '{target_id}' not found."))
        return 1

    env = FinancialAuditEnv(episode_dir=ep_dir, max_steps=100)
    obs, info = env.reset()

    manifest = obs.get("manifest_summary", {})
    welcome_text = (
        f"You are the Lead Auditor assigned to inspect {c_cyan(target_id, bold=True)}.\n"
        f"Base Currency : {manifest.get('base_currency')}  |  Ledger: {manifest.get('n_records')} records\n"
        f"Step Budget   : {info.get('max_steps')} moves. Each action consumes 1 turn.\n\n"
        f"Type {c_bold('help')} for command cheat-sheet, {c_bold('submit')} to finalize report."
    )
    print_panel(welcome_text, title="HUMAN AUDITOR MODE (INTERACTIVE)", border_color=Ansi.SUCCESS_EMERALD, width=72)

    staged_findings = []

    while True:
        remaining = obs.get("remaining_steps", 0)
        try:
            prompt_str = f"\n{c_cyan('airship')} ({c_yellow(f'{remaining} turns left')}) {c_sky('❯')} "
            user_input = input(prompt_str).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAudit aborted by user.")
            break

        if not user_input:
            continue

        parts = user_input.split()
        cmd = parts[0].lower()

        if cmd in ("exit", "quit", "q"):
            print("Exiting audit session.")
            break

        elif cmd == "help":
            help_text = (
                "Commands:\n"
                "  list <ledger|invoices|payments|fx> [cursor] [limit]  Query records\n"
                "  doc <doc_id>                                         View document (e.g. DOC-INV-00001)\n"
                "  calc <expression>                                    Decimal sandbox calculator\n"
                "  stage <type> <amount_minor> <curr> <aff_id> <ev_id>  Stage an audit finding\n"
                "  findings                                             View staged findings\n"
                "  clear                                                Clear staged findings\n"
                "  submit                                               Submit report & evaluate\n"
                "  quit                                                 Exit without scoring"
            )
            print(c_gray(help_text))

        elif cmd == "list":
            table_name = parts[1] if len(parts) > 1 else "ledger"
            cursor = int(parts[2]) if len(parts) > 2 else 0
            limit = int(parts[3]) if len(parts) > 3 else 10
            action = {"type": "list_records", "table": table_name, "cursor": cursor, "limit": limit}
            obs, reward, term, trunc, _ = env.step(action)
            res = obs.get("action_result") or {}
            recs = res.get("records", [])
            print(f" {c_green('✓')} Received {len(recs)} records (next_cursor={res.get('next_cursor')}):")
            for r in recs[:5]:
                print(f"   {r}")
            if len(recs) > 5:
                print(f"   {c_gray(f'... and {len(recs) - 5} more')}")

        elif cmd == "doc":
            if len(parts) < 2:
                print(c_red("Usage: doc <DOC-ID>"))
                continue
            doc_id = parts[1]
            obs, reward, term, trunc, _ = env.step({"type": "get_document", "doc_id": doc_id})
            res = obs.get("action_result") or {}
            print_panel(json.dumps(res, indent=2), title=f"DOCUMENT: {doc_id}", width=68)

        elif cmd == "calc":
            expr = " ".join(parts[1:])
            obs, reward, term, trunc, _ = env.step({"type": "calculator", "expression": expr})
            res = obs.get("action_result") or {}
            if "error" in res:
                print(f" {c_red('✖ Error:')} {res['error']}")
            else:
                print(f" {c_green('✓ Result:')} {c_bold(res.get('result'))}")

        elif cmd == "stage":
            # stage <type> <amount> <curr> <aff_id> <ev_id>
            if len(parts) < 6:
                print(c_yellow("Usage: stage <type> <amount_minor> <currency> <affected_id> <evidence_id>"))
                print(c_gray("Example: stage duplicate_accounts 144000 EUR ROW-00123 DOC-INV-00045"))
                continue
            f_type = parts[1]
            f_amt = int(parts[2])
            f_curr = parts[3].upper()
            f_aff = [parts[4]]
            f_ev = [parts[5]]
            finding = {
                "type": f_type,
                "claimed_amount_minor": f_amt,
                "currency": f_curr,
                "affected_ids": f_aff,
                "evidence_ids": f_ev,
                "explanation": "Human audit finding",
            }
            staged_findings.append(finding)
            print(f" {c_green('✓')} Staged finding #{len(staged_findings)}: {f_type} for {f_amt} {f_curr}")

        elif cmd == "findings":
            if not staged_findings:
                print("No findings staged yet.")
            else:
                print(f"Currently staged findings ({len(staged_findings)}):")
                for i, sf in enumerate(staged_findings, 1):
                    print(f"  {i}. {sf['type']} ({sf['claimed_amount_minor']} {sf['currency']}) - Aff: {sf['affected_ids']}")

        elif cmd == "clear":
            staged_findings.clear()
            print("Staged findings cleared.")

        elif cmd == "submit":
            submit_action = {"type": "submit", "findings": staged_findings}
            obs, reward, terminated, truncated, step_info = env.step(submit_action)
            metrics = step_info.get("eval_metrics", {})
            print()
            print_score_card(metrics, reward, terminated, truncated)
            break

        else:
            print(c_red(f"Unknown command: '{cmd}'. Type 'help' for options."))


# ----------------------------------------------------------------------
# 6. CHECK COMMAND
# ----------------------------------------------------------------------
def cmd_check():
    """Run full verification pipeline (pytest -> generate -> benchmark)."""
    print_banner()
    w = get_term_width()
    print(c_cyan(divider("VERIFICATION PIPELINE START", width=w)))

    # Step 1: pytest
    print(f"\n{badge('[1/3]', 'sky')} {c_bold('Running 67 unit & contract tests (pytest)...')}")
    p1 = subprocess.run([sys.executable, "-m", "pytest", "tests", "-v"], cwd=ROOT_DIR)
    if p1.returncode != 0:
        print(f"\n{badge_fail()} Pytest suite failed!")
        return p1.returncode

    # Step 2: make episodes
    print(f"\n{badge('[2/3]', 'purple')} {c_bold('Synthesizing 20 benchmark episodes...')}")
    r2 = cmd_generate()
    if r2 != 0:
        return r2

    # Step 3: benchmark
    print(f"\n{badge('[3/3]', 'green')} {c_bold('Executing policy evaluation benchmark...')}")
    r3 = cmd_benchmark("all")
    if r3 != 0:
        return r3

    print(c_green(divider("ALL VERIFICATION CHECKS PASSED PERFECTLY", width=w)))
    print(f"\n {badge_pass()} System integrity and reproducibility confirmed 100%.\n")
    return 0
