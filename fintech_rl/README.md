# Fintech RL: Воспроизводимая RL-среда для ИИ-аудитора финансовой отчётности

MVP воспроизводимой среды обучения с подкреплением (Reinforcement Learning) для агента-аудитора финансовой отчётности предприятий. Среда генерирует реалистичные синтетические компании с бухгалтерскими и транзакционными расхождениями. Агент расследует проводки и документы через изолированные инструменты (`list_records`, `get_record`, `get_document`, `calculator`) и отправляет подтверждённые доказательствами выводы через `submit`.

## Ограничения среды
- **Изоляция:** Без сетевого доступа, без внешних API, без GPU.
- **Стек:** Python 3.11+ (стандартная библиотека + `pydantic` + `numpy`).
- **Бюджет:** < 2 CPU, < 4 GB RAM, < 60 секунд на эпизод, лимит 100 шагов.
- **Синтетические данные:** Все наименования контрагентов, счетов, инвойсов и платежей вымышлены.
- **Информационная безопасность:** Закрытые файлы (`truth.json`, `provenance.json`, сиды) защищены от утечек в observations, ошибки и логи.

---

## Быстрый старт

### Единая команда проверки
Для запуска полного цикла проверки выполните скрипт:
```bash
./scripts/check.sh
```
Скрипт выполняет:
1. Запуск unit/contract тестов (`pytest`).
2. Генерацию 10 train и 10 dev синтетических эпизодов (`scripts/make_episodes.py`).
3. Запуск 4 тестовых политик (`oracle`, `simple_reconciler`, `random_explorer`, `mark_all`) с записью `trajectories.jsonl`.
4. Печать таблицы метрик (P, R, F1, Return, Steps, Time).

---

## Запуск в Docker

Для воспроизведения проверки в изолированном контейнере без доступа к сети:

```bash
# 1. Сборка контейнера
docker build -t fintech-rl:latest .

# 2. Запуск без сети
docker run --rm --network none fintech-rl:latest ./scripts/check.sh
```

Пример `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir pydantic numpy pytest

COPY . .
RUN chmod +x scripts/check.sh

CMD ["./scripts/check.sh"]
```

---

## Архитектура репозитория

```
fintech_rl/
  pyproject.toml            # Метаданные и зависимости
  README.md                 # Документация и запуск
  DESIGN.md                 # Архитектурные решения и допуски
  src/fintech_rl/
    schema.py               # Pydantic-модели (манифест, проводки, инвойсы, платежи, FX)
    generator/              # Генератор синтетических компаний и ошибок
      company.py            # Синтетический бизнес-цикл компании
      errors.py             # 4 типа ошибок (E1-E4) и 2 сценария взаимодействия (X1-X2)
      documents.py          # Рендер открытых и закрытых артефактов
      provenance.py         # История причинных изменений
    env/                    # Среда выполнения (Gymnasium-совместимый контракт)
      environment.py        # reset/step, терминальная оценка
      actions.py            # list_records, get_record, get_document, calculator, submit
      observation.py        # Изолированная проекция observation
    scoring/                # Оценка результатов
      matcher.py            # Взаимно однозначное сопоставление (бипарте match)
      reward.py             # P, R, F1, штраф за шаги
      tolerances.py         # Точные Decimal FX и округления
    policies/               # Опорные политики
      oracle.py             # Эталонная политика (F1 = 1.0)
      simple_reconciler.py  # Простой эвристический алгоритм
      random_explorer.py    # Случайное исследование
      mark_all.py           # Атака массовым спамом
  tests/                    # Набор тестов (генератор, контракт, атаки, воспроизводимость)
  scripts/
    check.sh                # Единая команда верификации
    make_episodes.py        # Генератор 20 эпизодов
    run_policies.py         # Запуск политик и сбор траекторий
  episodes/                 # Сгенерированные эпизоды
    train/ (10 эпизодов)
    dev/   (10 эпизодов)
  trajectories.jsonl        # Лог шагов агентов
```
