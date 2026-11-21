# Airship — итоговый технический аудит

Дата: 21 ноября 2026 года. Репозиторий: `C:\Users\Avashka\OneDrive\Desktop\airship`.

Итог: Python 3.11.18; 516 тестов выполнено, 516 PASS, 0 FAIL, 0 SKIP. Полный pipeline через установленный airship.exe выполнен успешно даже при CP1251/PYTHONUTF8=0.

## A. Исправления и выбор решений

Исходный baseline: 67/67 тестов PASS; Git clean, Arman_fixes и main указывали на b45d8165f10d9dcbdf0e6d6a03db5140fedcf9d1. Отдельного файла официального ТЗ среди изученных файлов airship не обнаружено; использованы README, DESIGN, SUBMISSION, схемы, исходники и тесты. Внешняя спецификация не выдумывалась.

Сохранена архитектура генератор → документы → ограниченный API → matcher → terminal reward. Формула `clip(2*F1 - 1 - 0.002*inspection_steps, -1, 1)` и допуск 1 minor unit не изменены; partial credit не добавлен. Существующие тесты не удалены и не ослаблены.

X1: два связанных issues (E2 в исходной валюте и E3 в USD) на одном платеже и его clearing-записях на последней секунде периода. E3 применяется к фактически распределённой части; доказательства включают публичный FX record. X2: один исходный счёт, исходная пара и её копия в следующем периоде; E1 и E4 относятся к одной операции. Каждая независимая инъекция резервирует семью документов.

Refund: положительная кредит-нота с related_invoice_id, Dr Revenue/Cr AR; возврат денег с direction=refund, Dr AR/Cr Cash. Суммы/валюты/даты связаны с первичной операцией, ложного truth issue нет. Новые поля необязательны, старые документы читаются.

Дополнительный stress выявил дефект сверх исходных тестов: 12 E3 не удавались на 35/500 seed из-за недостатка независимых валютных семей. Исправлено структурным разнообразием обычной генерации, без подгонки seed или повторных попыток. Повторная проверка: 500/500 PASS. Явные ограничения бизнес-сценариев сохраняют смысл; невозможный запрос инъекции отклоняется атомарно.

До замены данных сохранён `work/baseline-artifacts.zip` с исходными episodes и trajectories. Все 20 кандидатов проходят валидацию до публикации. Неизвестные/сторонние файлы каталогов не удаляются; ошибки записи откатывают заменённые артефакты.

### Исходники, workflow и тесты

| Полный путь | Изменение и причина |
|---|---|
| `C:\Users\Avashka\OneDrive\Desktop\airship\.dockerignore` | Исключены .venv, work, Git, кэши, архивы и .env из Docker build context. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\.gitattributes` | Единый LF для текстовых файлов; предотвращение CRLF-сбоев Linux shell и расхождений артефактов. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\.gitignore` | Исключён work/; локальные runtime, резервные копии и кэши не попадают в Git. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\AUDIT_REPORT.md` | Этот отчёт: изменения каждого файла, проверенные требования, команды, Git и остаточные риски. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\DESIGN.md` | Описаны финансовые модели X1/X2/возвратов, подсчёт issues и границы доверия API. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\Dockerfile` | Установка самого пакета и зависимостей, нормализация shell-скрипта; контейнерная проверка не выполнена. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\Makefile` | Убрано устаревшее фиксированное число тестов; основные Linux-команды сохранены. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\README.md` | Документированы reset/config, null/FX, диапазоны, возвраты и актуальные измеренные метрики. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\SUBMISSION.md` | Актуализированы результаты; убраны неподтверждённые баллы жюри; явно указан непройденный Docker. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\scripts\check.sh` | Полный Linux-пайплайн; временные pytest-данные в work; актуальное описание тестов. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\scripts\make_episodes.py` | Общий builder и staged validation/publish; существующие каталоги и сторонние результаты не удаляются. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\src\fintech_rl\cli\commands.py` | 0–12 issues в 20 конфигурациях; полная валидация перед публикацией и rollback; eval benchmark, атомарные logs без Oracle. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\src\fintech_rl\cli\main.py` | UTF-8 stdout/stderr для Windows-перенаправления CP1251; UTF-8/capture-потоки сохраняются. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\src\fintech_rl\env\actions.py` | Единый FX natural ID в list/get, detached public copies, точные Decimal literals и ограниченный AST calculator. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\src\fintech_rl\env\environment.py` | Полноценный in-memory reset(seed), очистка и приоритет источников, null compatibility, 1–100 шагов, fail-closed mode, безопасные ошибки и terminal penalties. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\src\fintech_rl\env\observation.py` | Allowlist полей policy; скрытые метаданные не проецируются в observation. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\src\fintech_rl\generator\company.py` | Фактические границы проводок/документов, ограниченные отдельные расходы, Decimal FX, документальные возвраты, гарантированные 12 валютных семей в обычной конфигурации. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\src\fintech_rl\generator\documents.py` | Явный CSV null; JSON null; канонические UTF-8/LF артефакты для Windows/Linux. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\src\fintech_rl\generator\episode.py` | Единый builder для среды и CLI без временных файлов, проверка config и запись приватных параметров воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\src\fintech_rl\generator\errors.py` | Настоящие связанные X1/X2, валютный clearing, уникальные IDs, резервирование семейств, атомарные batches и лимит 12 issues. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\src\fintech_rl\generator\provenance.py` | Версия 2.0.0, конфигурация и порядок инъекций сохраняются только в закрытом provenance. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\src\fintech_rl\generator\validator.py` | Независимое воспроизведение сумм/доказательств; баланс операций, ссылки/семьи, cut-off, даты, размеры и согласованность provenance. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\src\fintech_rl\identifiers.py` | Стабильный публичный FX ID date:source_currency:target_currency без новой колонки CSV. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\src\fintech_rl\policies\simple_reconciler.py` | Полная пагинация и обе пары проводок в доказательствах; совместимость с усиленным matcher evidence contract. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\src\fintech_rl\schema.py` | Только необязательные поля credit note/refund/provenance; запрет пустых и oversized truth evidence sets. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\tests\test_cli_extended.py` | 11 случаев: safe staging/rollback/logs, разнообразие конфигураций и Windows CP1251/UTF-8. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\tests\test_data_integrity.py` | 23 случая: serialization, corrupted truth/evidence/FX/provenance, даты, необъявленный cut-off, чужие семьи, полный reconciler evidence, LF и hash-seed reproducibility. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\tests\test_env_extended.py` | 47 случаев: generated reset/reuse, modes, budgets, private-data denials, FX, aliasing, calculator, null и missing truth. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\tests\test_generator_extended.py` | 368 случаев: размеры, refunds, X1/X2, 0–12 issues, атомарность, 256 seed с 12 E3 и сложные порядки инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\trajectories.jsonl` | Перегенерированы 381 публичная запись для 60 policy/episode траекторий: три обычные политики, eval reward=0, без Oracle; все записи точно воспроизведены. |

### Каждый изменённый файл датасета

Регенерация согласованная и воспроизводимая; существующие policy.json и truth чистых эпизодов не изменялись, если их байты уже совпадали. Ниже перечислен каждый действительно изменённый файл.

| Полный путь | Изменение и причина |
|---|---|
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_01\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_01\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_01\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_01\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_01\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_01\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_02\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_02\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_02\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_02\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_02\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_02\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_03\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_03\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_03\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_03\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_03\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_03\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_04\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_04\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_04\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_04\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_04\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_04\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_04\truth.json` | Согласованный закрытый эталон с полными доступными доказательствами и one-to-one issues. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_05\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_05\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_05\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_05\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_05\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_05\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_05\truth.json` | Согласованный закрытый эталон с полными доступными доказательствами и one-to-one issues. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_06\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_06\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_06\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_06\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_06\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_06\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_06\truth.json` | Согласованный закрытый эталон с полными доступными доказательствами и one-to-one issues. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_07\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_07\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_07\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_07\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_07\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_07\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_07\truth.json` | Согласованный закрытый эталон с полными доступными доказательствами и one-to-one issues. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_08\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_08\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_08\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_08\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_08\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_08\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_08\truth.json` | Согласованный закрытый эталон с полными доступными доказательствами и one-to-one issues. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_09\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_09\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_09\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_09\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_09\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_09\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_09\truth.json` | Согласованный закрытый эталон с полными доступными доказательствами и one-to-one issues. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_10\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_10\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_10\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_10\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_10\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_10\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\dev\dev_ep_10\truth.json` | Согласованный закрытый эталон с полными доступными доказательствами и one-to-one issues. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_01\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_01\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_01\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_01\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_01\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_01\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_02\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_02\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_02\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_02\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_02\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_02\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_03\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_03\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_03\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_03\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_03\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_03\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_03\truth.json` | Согласованный закрытый эталон с полными доступными доказательствами и one-to-one issues. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_04\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_04\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_04\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_04\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_04\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_04\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_04\truth.json` | Согласованный закрытый эталон с полными доступными доказательствами и one-to-one issues. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_05\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_05\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_05\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_05\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_05\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_05\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_05\truth.json` | Согласованный закрытый эталон с полными доступными доказательствами и one-to-one issues. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_06\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_06\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_06\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_06\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_06\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_06\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_06\truth.json` | Согласованный закрытый эталон с полными доступными доказательствами и one-to-one issues. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_07\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_07\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_07\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_07\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_07\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_07\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_07\truth.json` | Согласованный закрытый эталон с полными доступными доказательствами и one-to-one issues. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_08\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_08\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_08\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_08\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_08\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_08\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_08\truth.json` | Согласованный закрытый эталон с полными доступными доказательствами и one-to-one issues. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_09\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_09\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_09\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_09\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_09\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_09\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_09\truth.json` | Согласованный закрытый эталон с полными доступными доказательствами и one-to-one issues. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_10\fx.csv` | Повторная генерация курсов Decimal с тем же seed и новой версией генератора; формат четырёх колонок сохранён. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_10\invoices.jsonl` | Обновлённые первичные счета и связанные положительные кредит-ноты с необязательными метаданными. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_10\ledger.csv` | Перегенерация согласованных проводок, возвратов и контролируемых ошибок; явный null и LF. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_10\manifest.json` | Фактические количества проводок/документов после всех инъекций. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_10\payments.jsonl` | Обновлённые full/split receipts и связанные возвратные платежи; согласованные даты и валюты. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_10\provenance.json` | Причинные снимки, seed, версия 2.0.0, config и порядок ошибок для воспроизведения. |
| `C:\Users\Avashka\OneDrive\Desktop\airship\episodes\train\train_ep_10\truth.json` | Согласованный закрытый эталон с полными доступными доказательствами и one-to-one issues. |

## B. Проверка требований

| Требование | Статус | Доказательство |
|---|---|
| reset(seed) | PASS | test_env_extended: seed42 без каталога, повторные reset, одинаковые действия, новый seed, directory priority, отсутствие I/O. |
| 200–2000 проводок | PASS | generator boundary tests; 300 новых seed: фактически 200–420; итоговый датасет 208–260. |
| 20–200 документов | PASS | forced unpaid20/full100/split66/refund50; 300 seed: фактически 20–200; итоговый датасет 94–118. |
| X1 | PASS | generator_extended: source allocation+real FX+boundary, общая семья, два issues, баланс и доступные evidence. |
| X2 | PASS | generator_extended: original+same-invoice duplicate in next period, два one-to-one issues и snapshots. |
| Refunds | PASS | clean refund tests, credit-note/refund reconciliation, отсутствие truth issues. |
| 0–12 ошибок | PASS | каждая величина 0–12 в тестах/20 конфигурациях; 300 mixed/boundary seed; 500 seed с 12 E3. |
| null | PASS | CSV literal null, JSON None, legacy blanks, renderer/reader/validator/policy round trips. |
| get_record fx | PASS | natural ID в list/get, неизвестный ID, неизвестная таблица, расход шага, row permutation и duplicate-key rejection. |
| Zero leakage через API/trajectories | PASS | private-file/path denials, policy allowlist, detached copies; 381 записей точно replayed, без Oracle/seed/evaluator данных, rewards0. |
| Reward / oracle / атаки | PASS | прежние matcher/reward attacks + stress300: Oracle0.998, MarkAll−1, дубли/валюта/неполные evidence штрафуются. |
| Лимит100 и pagination50 | PASS | старые и новые env tests, invalid final action, budget validation, stable pages. |
| Docker | FAIL — не выполнен | docker отсутствует в PATH и стандартном Docker Desktop пути; build/run не выполнялись. Только static review, bash -n, compileall, .dockerignore и Dockerfile edits. |

## C. Выполненные проверки

- Baseline: 67 PASS / 0 FAIL. Финальный полный прогон: **516 PASS / 0 FAIL / 0 SKIP**, pytest 53.31 s. Новых тестовых случаев: 449.
- Python3.11.18; pydantic2.10.4, numpy2.2.1, pytest8.3.4; зависимости из pyproject.toml. Системный Python3.13 не использовался.
- Генерация всех20 эпизодов и запуск4политик: PASS; пять чистых эпизодов, остальные имеют каждый уровень1–12.
- Дополнительные300seed: 10000–10259 и20000–20039; каждый случай проверен через файлы/validator, доступность evidence, Oracle и MarkAll; повторные SHA-256 и публичный replay.
- Отдельные500seed: 0–499, запрос12E3, 500PASS / 0FAIL после исправления. Эти seed не пересекаются с300внешними stressseed.
- Проверены разные PYTHONHASHSEED в независимых процессах; канонический UTF8/LF, денежное округление Decimal.
- git diff --check: PASS; bash -n scripts/check.sh: PASS; compileall src/scripts: PASS; installed CLI help/inspect под CP1251: PASS.

Команды из корня airship (PowerShell):

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp=work/pytest-baseline
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp=work/pytest-final
.\.venv\Scripts\python.exe scripts/make_episodes.py
.\.venv\Scripts\python.exe scripts/cli.py check
$env:PYTHONIOENCODING='cp1251'; $env:PYTHONUTF8='0'; $env:PYTHONHASHSEED='0'
.\.venv\Scripts\airship.exe check
.\.venv\Scripts\python.exe work/stress_generations.py
.\.venv\Scripts\python.exe work/final_verification.py
.\.venv\Scripts\python.exe -m compileall -q src scripts
& "C:\Program Files\Git\bin\bash.exe" -n scripts/check.sh
git -c core.safecrlf=false diff --check
```

Максимальный E3 sweep выполнен inline Python, итог в work/max-fx-results.json. Остальные доказательства: work/baseline-tests.txt, work/baseline-dataset.json, work/pipeline-final.txt, work/stress-results.json, work/final-verification.json, work/diff-check.txt. Служебные файлы work и .venv игнорируются Git. Локальная .venv использует Python runtime в work/python; удалять его при дальнейшем использовании этой .venv нельзя.

Измеренные политики (mean по20эпизодам; время машины не является гарантией CPU/RAM):

| Policy | Precision | Recall | F1 | Reward | Steps |
|---|---:|---:|---:|---:|---:|
| oracle | 1.000 | 1.000 | 1.000 | 0.9980 | 1.00 |
| simple_reconciler | 0.850 | 0.457 | 0.541 | 0.0697 | 7.05 |
| random_explorer | 0.250 | 0.250 | 0.250 | -0.5050 | 10.00 |
| mark_all | 0.250 | 0.250 | 0.250 | -1.0000 | 2.00 |

Невалидный spam-report получает обязательный −1 независимо от диагностического F1 на пустом эталоне. Награды таблицы читает evaluator harness; политикам и публичному eval-журналу возвращается0.

## D. Git

- Текущая ветка: **fix/generator**, создана от актуальной локальной main.
- main до/после: `b45d8165f10d9dcbdf0e6d6a03db5140fedcf9d1` — не изменена. HEAD также остался на исходном commit; новых commits не создавалось.
- Изменённых tracked-файлов: 156; новых файлов: 9. Полный перечень каждого файла выше. Неожиданных изменений внутри репозитория не обнаружено.
- Пользовательских незакоммиченных изменений в baseline не было; Uiren и соседние проекты не открывались и не изменялись.
- Никаких push, merge, PR, fetch или удаления прежних архивов не выполнялось. Существующие архивы submission сохранены; они устарели.
- Готовность: локальные изменения готовы к code review; перед отправкой/PR рекомендуется контейнерная проверка. Коммит и публикация остаются за владельцем.

Новые файлы:

- `C:\Users\Avashka\OneDrive\Desktop\airship\.dockerignore`
- `C:\Users\Avashka\OneDrive\Desktop\airship\.gitattributes`
- `C:\Users\Avashka\OneDrive\Desktop\airship\AUDIT_REPORT.md`
- `C:\Users\Avashka\OneDrive\Desktop\airship\src\fintech_rl\generator\episode.py`
- `C:\Users\Avashka\OneDrive\Desktop\airship\src\fintech_rl\identifiers.py`
- `C:\Users\Avashka\OneDrive\Desktop\airship\tests\test_cli_extended.py`
- `C:\Users\Avashka\OneDrive\Desktop\airship\tests\test_data_integrity.py`
- `C:\Users\Avashka\OneDrive\Desktop\airship\tests\test_env_extended.py`
- `C:\Users\Avashka\OneDrive\Desktop\airship\tests\test_generator_extended.py`

## E. Остаточные риски и действия перед сдачей

1. **Средний: Docker/Linux не запущен.** На машине с Docker выполнить `docker build -t airship:latest .`, затем `docker run --rm --network none airship:latest ./scripts/check.sh`. Не считать этот пункт PASS до реального выполнения. Лимиты <2CPU/<4GB отдельно не профилировались.
2. **Средний: старые submission-архивы содержат старую версию.** Сохранены намеренно. Перед отправкой собрать новый архив из текущих исходников/episodes/безопасных trajectories, исключив .git/.venv/work/.env и прежние архивы.
3. **Низкий: формального внешнего ТЗ в checkout нет.** Перед сдачей сверить формат с предоставленным организаторами оригиналом. Самооценка баллов не заменяет проверку жюри.
4. **Низкий: модель остаётся синтетической и с фиксированным отчётным окном января2025.** Это существующая архитектура; общие календари и реальные OCR/банковские источники не добавлялись.
5. **Граница доверия:** zero-leak PASS относится к observation/action API и новым trajectories. Произвольному Python-коду с доступом к объекту env/локальному диску нужен отдельный процесс/контейнер; встроенный API не заявляется OS sandbox.

Критичных известных незакрытых дефектов в проверенной области не осталось. Конечные проверки не являются доказательством всех возможных seed; для скрытых комбинаций применены структурные ограничения, полные связи, атомарность и независимое воспроизведение сумм.
