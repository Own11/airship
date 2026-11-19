import json
import time
from pathlib import Path
from typing import List, Dict, Any
from fintech_rl.env.environment import FinancialAuditEnv
from fintech_rl.policies.random_explorer import RandomExplorerPolicy
from fintech_rl.policies.simple_reconciler import SimpleReconcilerPolicy
from fintech_rl.policies.mark_all import MarkAllPolicy
from fintech_rl.policies.oracle import OraclePolicy


def run_policy_on_episode(env: FinancialAuditEnv, policy: Any, episode_dir: Path, trajectory_file=None) -> Dict[str, Any]:
    t0 = time.time()
    obs, info = env.reset(config={"episode_dir": episode_dir})
    if hasattr(policy, "reset"):
        policy.reset()

    terminated = False
    truncated = False
    step = 0
    final_reward = 0.0
    final_metrics = {}

    while not (terminated or truncated):
        step += 1
        action = policy.act(obs)
        next_obs, reward, terminated, truncated, step_info = env.step(action)

        if trajectory_file:
            # Trajectory record: NO truth, NO provenance
            record = {
                "episode_id": info["episode_id"],
                "step": step,
                "action": action,
                "observation": next_obs,
                "reward": reward,
                "terminated": terminated,
                "truncated": truncated
            }
            trajectory_file.write(json.dumps(record) + "\n")

        obs = next_obs
        final_reward = reward
        if "eval_metrics" in step_info:
            final_metrics = step_info["eval_metrics"]

    elapsed = time.time() - t0
    return {
        "episode_id": info["episode_id"],
        "steps": step,
        "time": elapsed,
        "reward": final_reward,
        "p": final_metrics.get("precision", 0.0),
        "r": final_metrics.get("recall", 0.0),
        "f1": final_metrics.get("f1", 0.0)
    }


def main():
    root_dir = Path(__file__).resolve().parent.parent
    episodes_dir = root_dir / "episodes"
    trajectories_path = root_dir / "trajectories.jsonl"

    train_eps = sorted(list((episodes_dir / "train").glob("train_ep_*")))
    dev_eps = sorted(list((episodes_dir / "dev").glob("dev_ep_*")))
    all_eps = train_eps + dev_eps

    policies = [
        ("oracle", lambda ep: OraclePolicy(episode_dir=ep)),
        ("simple_reconciler", lambda ep: SimpleReconcilerPolicy()),
        ("random_explorer", lambda ep: RandomExplorerPolicy(seed=42)),
        ("mark_all", lambda ep: MarkAllPolicy()),
    ]

    print(f"Running 4 policies across {len(all_eps)} episodes (10 train + 10 dev)...")
    env = FinancialAuditEnv()

    with open(trajectories_path, "w", encoding="utf-8") as traj_file:
        summary_results = []

        for pol_name, pol_factory in policies:
            total_p, total_r, total_f1, total_ret, total_steps, total_time = 0.0, 0.0, 0.0, 0.0, 0, 0.0
            n_eps = len(all_eps)

            for ep_dir in all_eps:
                policy = pol_factory(ep_dir)
                res = run_policy_on_episode(env, policy, ep_dir, trajectory_file=traj_file)
                total_p += res["p"]
                total_r += res["r"]
                total_f1 += res["f1"]
                total_ret += res["reward"]
                total_steps += res["steps"]
                total_time += res["time"]

            summary_results.append({
                "policy": pol_name,
                "P": total_p / n_eps,
                "R": total_r / n_eps,
                "F1": total_f1 / n_eps,
                "return": total_ret / n_eps,
                "avg_steps": total_steps / n_eps,
                "total_time": total_time
            })

    # 1. Diagnostic metrics table (P, R, F1, Steps, Time)
    print("\n" + "="*70)
    print("                    ТАБЛИЦА ДИАГНОСТИКИ КАЧЕСТВА                    ")
    print("="*70)
    print(f"{'POLICY':<20} | {'PRECISION':<10} | {'RECALL':<8} | {'F1-SCORE':<9} | {'STEPS':<6} | {'TIME (s)':<8}")
    print("-" * 70)
    for row in summary_results:
        print(f"{row['policy']:<20} | {row['P']:<10.3f} | {row['R']:<8.3f} | {row['F1']:<9.3f} | {row['avg_steps']:<6.1f} | {row['total_time']:<8.2f}")
    print("="*70)

    # 2. RL Return / Reward table (separated from diagnostics)
    print("\n" + "="*50)
    print("             ТАБЛИЦА НАГРАД (RL RETURN)            ")
    print("="*50)
    print(f"{'POLICY':<20} | {'MEAN RETURN':<12} | {'STEPS':<6}")
    print("-" * 50)
    for row in summary_results:
        print(f"{row['policy']:<20} | {row['return']:<12.3f} | {row['avg_steps']:<6.1f}")
    print("="*50 + "\n")


if __name__ == "__main__":
    main()
