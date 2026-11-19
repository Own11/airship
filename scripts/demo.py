import sys
from pathlib import Path

# Add src to sys.path so the script runs directly from any working directory
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fintech_rl.env.environment import FinancialAuditEnv
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

    policy = SimpleReconcilerPolicy()
    policy.reset()

    step_count = 0
    terminated = False
    truncated = False

    while not (terminated or truncated):
        step_count += 1
        action = policy.act(obs)
        act_type = action.get("type")

        print_section(f"STEP {step_count}: AGENT ACTION -> [{act_type}]")
        if act_type == "list_records":
            print(
                f"Querying table '{action.get('table')}', "
                f"cursor={action.get('cursor')}, limit={action.get('limit')}"
            )
        elif act_type == "submit":
            findings = action.get("findings", [])
            print(f"Submitting audit findings report: {len(findings)} issue(s) detected")
            for idx, finding in enumerate(findings, 1):
                print(
                    f"  {idx}. Type: {finding['type']}, "
                    f"Amount: {finding['claimed_amount_minor']} {finding['currency']}, "
                    f"Evidence: {finding['evidence_ids']}"
                )

        obs, reward, terminated, truncated, step_info = env.step(action)

        if act_type == "list_records":
            res = obs.get("action_result") or {}
            print(
                f"Environment response: {len(res.get('records', []))} records returned, "
                f"next_cursor={res.get('next_cursor')}"
            )
        elif act_type == "submit":
            print_section("EVALUATOR SCORING & AUDIT VERDICT")
            metrics = step_info.get("eval_metrics", {})
            print(f"True Positives  (TP) : {metrics.get('tp')}")
            print(f"False Positives (FP) : {metrics.get('fp')}")
            print(f"False Negatives (FN) : {metrics.get('fn')}")
            print(f"Precision            : {metrics.get('precision', 0.0):.3f}")
            print(f"Recall               : {metrics.get('recall', 0.0):.3f}")
            print(f"F1-Score             : {metrics.get('f1', 0.0):.3f}")
            print(f"Terminal Return      : {reward:.4f}")
            print(f"Status               : terminated={terminated}, truncated={truncated}")

    print("\n" + "#" * 65)
    print("      DEMONSTRATION EPISODE COMPLETED SUCCESSFULLY")
    print("#" * 65 + "\n")


if __name__ == "__main__":
    run_demo()
