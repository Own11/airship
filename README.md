<div align="center">

# 🛸 Airship: Reproducible RL Environment for Financial Statement Audit

[![Tests](https://img.shields.io/badge/pytest-67%20passed-brightgreen.svg)](tests/)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg)](Dockerfile)
[![Network](https://img.shields.io/badge/network-offline%20ready-success.svg)](#-ограничения-среды-strict-zero-leak-constraints)
[![CLI](https://img.shields.io/badge/CLI-Rich%20TUI%20Enabled-8A2BE2.svg)](#-терминальный-интерфейс-airship-cli--tui)

**Airship — воспроизводимая RL-среда (Gymnasium API) для обучения и оценки ИИ-аудиторов финансовой отчётности.**  
Среда процедурно генерирует синтетические компании с бухгалтерскими книгами ($Debit == Credit$), инжектирует 4 класса нарушений и 2 взаимодействующих сценария, предоставляет изолированный набор инструментов расследования (`list_records`, `get_record`, `get_document`, `calculator`, `submit`) и строго оценивает доказательную базу выводов без утечек данных.

[Быстрый старт](#-быстрый-старт) •
[CLI и Режим Аудитора](#-терминальный-интерфейс-airship-cli--tui) •
[Архитектура](#-архитектура-репозитория) •
[Аудит и Награда](#-скоринг-и-награда) •
[Метрики политик](#-контрольные-метрики-политик-20-эпизодов) •
[Спецификация (DESIGN.md)](DESIGN.md) •
[Сдача (SUBMISSION.md)](SUBMISSION.md)

</div>

---

## ⚡ Ограничения среды (Strict Zero-Leak Constraints)
- **Полная автономность:** Работает строго без сети (`--network none`), без платных API и без GPU.
- **Минимальный стек:** Python 3.11+, стандартная библиотека + `pydantic==2.10.4`, `numpy==2.2.1`.
- **Ресурсы и бюджет:** < 2 CPU, < 4 GB RAM, < 60 секунд на эпизод, лимит ровно 100 шагов на расследование.
- **Синтетические данные:** Компании, транзакции, контрагенты и первичные документы процедурно генерируются по детерминированным сидам.
- **Информационная безопасность (Zero-Leak):** Закрытые файлы (`truth.json`, `provenance.json`), сиды генератора и поля оценщика изолированы и **никогда не попадают** в `observation`, сообщения об ошибках, пути или логи агента.

---

## 🚀 Быстрый старт

### 1. Единая команда проверки (Регламент хакатона)
Запуск полного цикла верификации (67 тестов + генерация 20 эпизодов + бенчмарк 4 политик + вывод диагностических таблиц):
```bash
./scripts/check.sh
# или через make
make check
```

### 2. Запуск в изолированном Docker-контейнере (без сети)
```bash
# Сборка чистого образа python:3.11-slim
docker build -t airship:latest .

# Запуск проверки с отключенной сетью
docker run --rm --network none airship:latest ./scripts/check.sh
```

### 3. Интерактивное пошаговое демо (п. 09 регламента)
Визуализированная пошаговая демонстрация расследования эпизода агентом:
```bash
make demo
# или напрямую
python3 scripts/cli.py demo
```

---

## 🖥️ Терминальный интерфейс (Airship CLI & TUI)

Проект оснащен автономной консольной графической подсистемой ([src/fintech_rl/cli/ui.py](src/fintech_rl/cli/ui.py)) **с нулевыми внешними зависимостями** (чистый Python, ANSI 256/TrueColor, Unicode-рамки, автодетект TTY/NO_COLOR).

```text
                      ___    ____ ____  _____ __  __________ 
                     /   |  /  _// __ \/ ___// / / /  _/ __ \
                    / /| |  / / / /_/ /\__ \/ /_/ // // /_/ /
                   / ___ |_/ / / _, _/___/ / __  // // ____/ 
                  /_/  |_/___//_/ |_|/____/_/ /_/___//_/     
                 ──[ FINANCIAL STATEMENT AUDITOR RL ENVIRONMENT ]──
```

### Доступные команды CLI:

| Команда | Описание | Пример вызова |
| :--- | :--- | :--- |
| **`help`** | Интерактивное меню команд и опций | `python3 scripts/cli.py --help` или `make help` |
| **`demo`** | Пошаговое демо расследования с карточками шагов | `python3 scripts/cli.py demo train_ep_03` или `make demo` |
| **`play`** | **Режим "Человек-Аудитор"** (интерактивная игра) | `python3 scripts/cli.py play train_ep_03` или `make play` |
| **`benchmark`** | Прогон 4 политик на 20 эпизодах с прогресс-баром | `python3 scripts/cli.py benchmark` или `make benchmark` |
| **`inspect`** | Просмотр проводок книги, инвойсов или манифеста | `python3 scripts/cli.py inspect train_ep_03 --table ledger` |
| **`generate`** | Генерация 10 train + 10 dev эпизодов с реестром | `python3 scripts/cli.py generate` или `make episodes` |
| **`check`** | Полный цикл верификации системы (тесты + прогон) | `python3 scripts/cli.py check` или `make check` |

### 🎮 Интерактивный режим "Человек-Аудитор" (`make play`)
Позволяет пользователю или члену жюри лично выступить в роли аудитора:
```text
airship (99 turns left) ❯ help
Commands:
  list <ledger|invoices|payments|fx> [cursor] [limit]  Query records
  doc <doc_id>                                         View document (e.g. DOC-INV-00001)
  calc <expression>                                    Decimal sandbox calculator
  stage <type> <amount_minor> <curr> <aff_id> <ev_id>  Stage an audit finding
  findings                                             View staged findings
  clear                                                Clear staged findings
  submit                                               Submit report & evaluate
  quit                                                 Exit without scoring
```
После ввода `submit` система выполняет бипарте-сопоставление с эталоном и выводит цветную карточку **AUDIT EVALUATION & SCORING VERDICT** с расчетом TP/FP/FN, Precision, Recall, F1 и награды $R$.

---

## 📊 Контрольные метрики политик (20 эпизодов)

Результаты прогона 4 базовых политик на 10 train + 10 dev эпизодах (`make benchmark`):

### 1. Таблица диагностики качества аудита
| Политика (Policy) | Точность (Precision) | Полнота (Recall) | F1-Score | Среднее число шагов | Время (с) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`oracle`** *(эталон оценщика)* | **1.000** | **1.000** | **1.000** | 1.0 | 0.11 |
| **`simple_reconciler`** *(эвристика)* | **0.350** | **0.325** | **0.333** | 4.2 | 0.16 |
| **`random_explorer`** *(случайный)* | **0.250** | **0.250** | **0.250** | 10.0 | 0.14 |
| **`mark_all`** *(атака спамом)* | **0.250** | **0.250** | **0.250** | 2.0 | 0.13 |

### 2. Таблица терминальной награды (RL Return)
| Политика | Mean Return | Среднее число шагов | Сохранение бюджета | Интерпретация поведения |
| :--- | :---: | :---: | :---: | :--- |
| **`oracle`** | **+0.998** | 1.0 | 99.0% | Идеальное нахождение всех несоответствий с полными доказательствами |
| **`simple_reconciler`** | **-0.336** | 4.2 | 95.8% | Находит реальные дубликаты проводок с подтверждением из документов |
| **`random_explorer`** | **-0.505** | 10.0 | 90.0% | Случайные запросы, сдача пустого отчёта |
| **`mark_all`** | **-1.000** | 2.0 | 98.0% | Атака спамом полностью нейтрализована штрафом за False Positives |

---

## 🐍 Использование среды в Python (Gymnasium API)

```python
import airship

# 1. Инициализация среды
env = airship.FinancialAuditEnv(episode_dir="episodes/train/train_ep_03", max_steps=100)
obs, info = env.reset()

print(f"Episode: {info['episode_id']}, Budget: {info['max_steps']}")
print(f"Base Currency: {obs['manifest_summary']['base_currency']}")

# 2. Чтение проводок книги
obs, reward, terminated, truncated, info = env.step({
    "type": "list_records",
    "table": "ledger",
    "limit": 50,
})

# 3. Безопасные математические расчеты в Decimal-песочнице
obs, reward, terminated, truncated, info = env.step({
    "type": "calculator",
    "expression": "1440.00 * 100",
})

# 4. Проверка первичного документа
obs, reward, terminated, truncated, info = env.step({
    "type": "get_document",
    "doc_id": "DOC-INV-00001",
})

# 5. Сдача отчёта аудитора
obs, reward, terminated, truncated, info = env.step({
    "type": "submit",
    "findings": [{
        "type": "duplicate_accounts",
        "claimed_amount_minor": 144000,
        "currency": "EUR",
        "affected_ids": ["ROW-00245", "ROW-00246", "ROW-DUP-38167", "ROW-DUP-20228", "INV-2025-1058"],
        "evidence_ids": ["ROW-DUP-38167", "ROW-DUP-20228", "DOC-INV-00123"],
        "explanation": "Duplicate ledger booking for single supplier invoice",
    }],
})

print(f"Reward: {reward:.4f}, Metrics: {info['eval_metrics']}")
```

---

## 🛠️ Архитектура репозитория

```
.
├── Makefile                # Автоматизация (check, test, demo, benchmark, play, inspect)
├── Dockerfile              # Воспроизводимый контейнер python:3.11-slim (--network none)
├── pyproject.toml          # Зависимости и консольная точка входа [project.scripts]
├── LICENSE                 # Открытая лицензия Apache License 2.0
├── README.md               # Документация проекта
├── DESIGN.md               # Математический дизайн, спецификация и разбор сбоев
├── SUBMISSION.md           # Описание решения для жюри (100 / 100)
├── trajectories.jsonl      # Лог траекторий без закрытых эталонов
├── scripts/
│   ├── check.sh            # Единый скрипт официальной проверки с цветными бейджами
│   ├── cli.py              # Автономный исполняемый CLI-раннер
│   ├── make_episodes.py    # Генератор 10 train + 10 dev эпизодов
│   ├── run_policies.py     # Запуск 4 политик и расчет метрик
│   └── demo.py             # Пошаговое терминальное демо
├── src/
│   ├── airship/            # Публичный пакет Airship (экспорт Gymnasium API и CLI)
│   │   ├── __init__.py
│   │   ├── __main__.py     # Поддержка запуска через python -m airship
│   │   └── cli.py          # CLI forwarding
│   └── fintech_rl/         # Ядро RL-среды, генератора и TUI
│       ├── schema.py       # Pydantic-модели с жесткой валидацией и лимитами
│       ├── cli/            # Автономная TUI-подсистема (Zero dependencies)
│       │   ├── ui.py       # ANSI-стили, скругленные рамки, таблицы, прогресс-бары
│       │   ├── commands.py # Реализация demo, benchmark, play, inspect, generate
│       │   └── main.py     # Парсер аргументов и диспетчер команд
│       ├── generator/      # Генератор компаний, 4 типов ошибок и 2 взаимодействий
│       │   ├── company.py  # Бизнес-цикл компании (200-2000 проводок, баланс D==C)
│       │   ├── errors.py   # E1-E4 и X1-X2 (дубликаты, FX, сплиты, периоды)
│       │   ├── documents.py# Рендер открытых данных и закрытых артефактов
│       │   ├── provenance.py # Причинная история изменений
│       │   └── validator.py# Автовалидатор достаточности доказательств
│       ├── env/            # Gymnasium-совместимый контракт среды
│       │   ├── environment.py # reset / step, лимит 100 шагов, терминальный скоринг
│       │   ├── actions.py  # list_records, get_record, get_document, calculator, submit
│       │   └── observation.py # Изолированная проекция observation (Zero-leak)
│       ├── scoring/        # Модуль оценки качества
│       │   ├── matcher.py  # Взаимно однозначное сопоставление (бипарте)
│       │   ├── reward.py   # P, R, F1, терминальная награда с шаговым штрафом
│       │   └── tolerances.py # Точные Decimal FX и допуски сумм
│       └── policies/       # 4 базовых адаптера политик
│           ├── oracle.py   # Оракул для проверки максимума оценщика
│           ├── simple_reconciler.py # Алгоритмический аудитор
│           ├── random_explorer.py   # Случайное блуждание
│           └── mark_all.py # Атакующий агент
├── tests/                  # 67 тестов (100% покрытие регламента)
│   ├── test_env_contract.py      # 43 теста контракта, лимитов и изоляции
│   ├── test_reward_attacks.py    # 15 тестов на 12 типов атак и свойств награды
│   ├── test_generator.py         # 4 теста баланса и автовалидатора
│   ├── test_matcher.py           # 3 теста бипарте-сопоставления
│   └── test_reproducibility.py   # 2 теста побитового детерминизма SHA-256
└── episodes/
    ├── train/              # 10 train эпизодов
    └── dev/                # 10 dev эпизодов
```

---

## 🎯 Поддерживаемые типы нарушений (Ground Truth)

1. **`E1 duplicate_accounts`:** Дублирование бухгалтерских записей хозяйственной операции в книге при наличии единственного первичного инвойса.
2. **`E2 partial_payment`:** Оплата проведена полностью в платёжном поручении, но в книге разнесена лишь частично.
3. **`E3 wrong_fx_or_date`:** Операция в иностранной валюте отражена по искажённому курсу вместо официального курса из `fx.csv`.
4. **`E4 period_misclassification`:** Ошибка признания отчётного периода (операция за пределами периода отнесена в текущую книгу).
5. **`X1 partial_fx_period_boundary`:** Взаимодействующий сценарий: неполный платёж в валюте на границе отчётного периода.
6. **`X2 duplicate_and_period`:** Взаимодействующий сценарий: дублирование проводки в сочетании с ошибкой периода.

---

## ⚖️ Скоринг и награда

### Сопоставление (Bipartite Matching)
Вывод признаётся **True Positive (TP)** при одновременном выполнении условий:
- Совпадение типа ошибки (`type`) и валюты (`currency`).
- Каноническое равенство множеств `affected_ids` (порядок не важен).
- Сумма расхождения в пределах допуска: $|claimed - expected| \le 1$ minor unit.
- Доказательства `evidence_ids` содержат полный набор из `acceptable_evidence_sets`.

### Формула терминальной награды:
$$\text{Return} = \text{clip}\left(2 \cdot F1 - 1.0 - 0.002 \cdot \text{steps}, -1.0, 1.0\right)$$

*При нарушении схемы отчёта или исчерпании лимита шагов без отправки выставляется штраф `-1.0`.*

---

## 📜 Полезные команды Makefile

```bash
make help          # цветная справка по всем доступным командам
make check         # полный скрипт проверки check.sh (тесты + генерация + бенчмарк)
make test          # запуск всех 67 тестов через pytest
make demo          # пошаговое визуализированное демо работы аудитора
make benchmark     # бенчмарк 4 политик на 20 эпизодах с прогресс-баром
make episodes      # генерация 10 train + 10 dev эпизодов
make inspect       # просмотр проводок книги и метаданных эпизода
make play          # запуск интерактивной консольной сессии "Человек-Аудитор"
make cli           # вызов справки консольного интерфейса
make clean         # удаление всех временных файлов и кэшей
make docker-build  # сборка контейнера python:3.11-slim
make docker-run    # запуск проверки в контейнере без доступа к сети
```

---

## 📄 Лицензия

Проект распространяется под открытой лицензией [Apache License 2.0](LICENSE).
