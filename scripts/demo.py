"""
Интерактивное демо работы среды и агента в терминале (п. 09 регламента).
Показывает один полный эпизод расследования:
1. Инициализация и чтение манифеста
2. Исследование книги (list_records)
3. Запрос первичных документов (get_document)
4. Расчёт расхождения на калькуляторе (calculator)
5. Отправка отчёта (submit) и оценка
"""

import sys
import time
from pathlib import Path
from fintech_rl.env.environment import FinancialAuditEnv
from fintech_rl.policies.simple_reconciler import SimpleReconcilerPolicy


def print_step(title: str, text: str = ""):
    print("\n" + "=" * 65)
    print(f"  >>> {title}")
    print("=" * 65)
    if text:
        print(text)


def main():
    root = Path(__file__).resolve().parent.parent
    ep_dir = root / "episodes" / "train" / "train_ep_03"
    if not ep_dir.exists():
        print(f"Ошибка: эпизод {ep_dir} не найден. Запустите scripts/make_episodes.py")
        sys.exit(1)

    print("\n" + "#" * 65)
    print("      ДЕМОНСТРАЦИЯ RL-СРЕДЫ ФИНАНСОВОГО АУДИТА (ДЕМО)")
    print("#" * 65)

    env = FinancialAuditEnv(episode_dir=ep_dir, max_steps=10)
    obs, info = env.reset()

    print_step("ШАГ 0: СТАРТ ЭПИЗОДА (RESET)", f"Эпизод: {info['episode_id']}\nБюджет шагов: {info['max_steps']}")
    print(f"Манифест компании: Базовая валюта={obs['manifest_summary']['base_currency']}, "
          f"Период={obs['manifest_summary']['period_start'][:10]} .. {obs['manifest_summary']['period_end'][:10]}, "
          f"Число проводок={obs['manifest_summary']['n_records']}")

    policy = SimpleReconcilerPolicy()
    policy.reset()

    step_count = 0
    terminated = False
    truncated = False

    while not (terminated or truncated):
        step_count += 1
        action = policy.act(obs)
        act_type = action.get("type")

        print_step(f"ШАГ {step_count}: ДЕЙСТВИЕ АГЕНТА -> [{act_type}]")
        if act_type == "list_records":
            print(f"Запрос таблицы '{action.get('table')}', limit={action.get('limit')}, cursor={action.get('cursor')}")
        elif act_type == "submit":
            findings = action.get("findings", [])
            print(f"Агент отправляет отчёт аудита: обнаружено выводов: {len(findings)}")
            for idx, f in enumerate(findings, 1):
                print(f"  {idx}. Тип: {f['type']}, Сумма: {f['claimed_amount_minor']} {f['currency']}, "
                      f"Доказательства: {f['evidence_ids']}")

        obs, reward, terminated, truncated, step_info = env.step(action)

        if act_type == "list_records":
            res = obs.get("action_result") or {}
            print(f"Ответ среды: получено записей: {len(res.get('records', []))}, следующий курсор: {res.get('next_cursor')}")
        elif act_type == "submit":
            print_step("ОЦЕНКА ЭПИЗОДА ОЦЕНЩИКОМ (EVALUATOR)")
            metrics = step_info.get("eval_metrics", {})
            print(f"True Positives  (TP) : {metrics.get('tp')}")
            print(f"False Positives (FP) : {metrics.get('fp')}")
            print(f"False Negatives (FN) : {metrics.get('fn')}")
            print(f"Точность (Precision) : {metrics.get('precision', 0):.3f}")
            print(f"Полнота (Recall)     : {metrics.get('recall', 0):.3f}")
            print(f"F1-Score             : {metrics.get('f1', 0):.3f}")
            print(f"Итоговая награда     : {reward:.4f}")
            print(f"Статус завершения    : terminated={terminated}, truncated={truncated}")

    print("\n" + "#" * 65)
    print("      ДЕМОНСТРАЦИОННЫЙ ЭПИЗОД УСПЕШНО ЗАВЕРШЁН")
    print("#" * 65 + "\n")


if __name__ == "__main__":
    main()
