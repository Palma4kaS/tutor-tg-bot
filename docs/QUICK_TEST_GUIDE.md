# ⚡ Быстрая инструкция по тестированию обновления

**Время выполнения:** ~15-30 минут

---

## 📋 Краткий чеклист

### 1️⃣ Тест миграции БД (5 минут)

```bash
cd /home/palma/RebornTgBot
source venv/bin/activate
python3 test_migration.py
```

**Ожидается:**
```
✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!
   Миграция безопасна для применения.
```

**Если провалилось** ❌ - СТОП! Не обновляйте сервер!

---

### 2️⃣ Проверка импортов (2 минуты)

```bash
# Тест 1: Импорт новых модулей
python3 -c "from bot_template.database.task_manager import TaskManager; print('✅ task_manager')"
python3 -c "from bot_template.database.task_executor import TaskExecutor; print('✅ task_executor')"
python3 -c "from bot_template.utils.logger import get_logger; print('✅ logger')"

# Тест 2: Проверка run.py
cd tutors/tutor_910518469
python3 -c "import sys; sys.path.insert(0, '.'); import run; print('✅ run.py')"
cd ../..
```

**Ожидается:** Все 4 команды выводят ✅

**Если ошибки** ❌ - проблемы с импортами, не обновляйте!

---

### 3️⃣ Локальный тест бота (10 минут)

**ОПЦИЯ A: Тест с существующим ботом**

```bash
# 1. Создайте бэкап
./backup_before_update.sh

# 2. Остановите одного бота
sudo systemctl stop tg-bot-910518469.service

# 3. Запустите вручную для проверки
cd tutors/tutor_910518469
python3 run.py
```

**Что проверить:**
- ✅ Бот запустился без ошибок
- ✅ Появилась папка `logs/` с файлами
- ✅ В консоли: "APScheduler started"
- ✅ Нет критических ошибок (ERROR, CRITICAL)

**Проверка логов:**
```bash
cat logs/bot.log | tail -30
cat logs/error.log
```

**Остановите бота:** `Ctrl+C`

---

**ОПЦИЯ B: Создать тестового бота**

```bash
# 1. Получите тестовый токен от @BotFather
# 2. Создайте тестового бота
python3 deploy_bot.py
# Выберите: 1 (Create new bot)
# ID: 999999999 (ваш ID)
# Token: (вставьте тестовый токен)

# 3. Запустите тестового бота
cd tutors/tutor_999999999
python3 run.py
```

**Протестируйте через Telegram:**
1. `/start` - регистрация
2. Создайте урок на +20 минут
3. Проверьте БД:
   ```bash
   sqlite3 tutor_bot.db "SELECT task_type, scheduled_time, status FROM scheduled_tasks;"
   ```
4. Должны быть 3 задачи: `lesson_starting_notification`, `lesson_start_notification`, `lesson_ending_notification`

---

### 4️⃣ Проверка системы задач (5 минут)

```bash
# Посмотрите задачи в БД
sqlite3 tutors/tutor_910518469/tutor_bot.db << 'EOF'
SELECT
    id,
    task_type,
    scheduled_time,
    status,
    retry_count
FROM scheduled_tasks
ORDER BY scheduled_time DESC
LIMIT 10;
EOF
```

**Что должно быть:**
- Задачи для будущих уроков
- Статус: `pending` (ожидают выполнения)
- `retry_count`: 0

---

### 5️⃣ Стресс-тест (опционально, 5 минут)

```bash
# Создайте несколько тестовых уроков через бота
# Затем проверьте:

sqlite3 tutors/tutor_910518469/tutor_bot.db << 'EOF'
-- Сколько задач создано
SELECT COUNT(*) as total_tasks FROM scheduled_tasks;

-- Группировка по типам
SELECT task_type, COUNT(*) as count
FROM scheduled_tasks
GROUP BY task_type;

-- Проверка индексов
EXPLAIN QUERY PLAN
SELECT * FROM scheduled_tasks
WHERE status='pending' AND scheduled_time <= datetime('now');
EOF
```

**Ожидается:**
- Задачи созданы для всех уроков (3 задачи на урок)
- В EXPLAIN должно быть "USING INDEX idx_tasks_status_time"

---

## ✅ Критерии успеха

Обновление БЕЗОПАСНО, если:
- ✅ `test_migration.py` прошел без ошибок
- ✅ Все импорты работают
- ✅ Бот запускается локально
- ✅ Создаются логи
- ✅ Задачи создаются в БД
- ✅ Нет критических ошибок в логах

---

## ❌ Критерии провала

НЕ ОБНОВЛЯЙТЕ, если:
- ❌ `test_migration.py` падает с ошибкой
- ❌ Ошибки импорта модулей
- ❌ Бот не запускается
- ❌ Задачи не создаются
- ❌ Много ошибок в `logs/error.log`
- ❌ В консоли: `ERROR`, `CRITICAL`, `Exception`

---

## 🚀 Если все OK - обновление на сервере

```bash
# 1. Создайте полный бэкап
./backup_before_update.sh

# 2. Остановите боты
./run_all_bots_systemd.sh stop

# 3. Обновите код на каждом инстансе
python3 deploy_bot.py
# Выберите: 2 (Update existing bot)
# Выберите каждого бота по очереди

# 4. Запустите боты
./run_all_bots_systemd.sh start

# 5. Проверьте статус
./run_all_bots_systemd.sh status

# 6. Проверьте логи (первые 2 часа)
watch -n 60 'tail -20 tutors/*/logs/error.log'
```

---

## 🔙 Если что-то пошло не так

```bash
# Быстрый откат
./restore_from_backup.sh YYYYMMDD_HHMMSS

# Или вручную:
./run_all_bots_systemd.sh stop
git checkout e7efa0a  # Предыдущая версия
# Восстановите БД из бэкапа
./run_all_bots_systemd.sh start
```

---

## 📊 Мониторинг после обновления

### Первые 2 часа:
```bash
# Каждые 15 минут
./run_all_bots_systemd.sh status
tail -50 tutors/*/logs/error.log

# Проверка задач
for db in tutors/*/tutor_bot.db; do
    echo "=== $db ==="
    sqlite3 "$db" "SELECT status, COUNT(*) FROM scheduled_tasks GROUP BY status;"
done
```

### Первые 24 часа:
- Проверяйте, что уведомления приходят вовремя
- Отслеживайте `logs/error.log` на новые ошибки
- Спрашивайте у пользователей (репетиторов), все ли работает

---

## ❓ Что может пойти не так

### Проблема 1: Двойные уведомления
**Симптом:** Ученики получают 2 одинаковых уведомления

**Причина:** Старая и новая система работают одновременно

**Решение:**
```bash
# Проверьте run.py, что старые cron-проверки отключены
grep -n "check_lessons_ending_soon\|check_lessons_starting" tutors/*/run.py
# Не должно быть вызовов этих функций
```

### Проблема 2: Уведомления не приходят
**Симптом:** Задачи в БД, но уведомления не отправляются

**Причина:** TaskExecutor не запустился

**Решение:**
```bash
# Проверьте логи
grep "TaskExecutor\|process_pending_tasks" logs/bot.log

# Проверьте, что в run.py есть запуск TaskExecutor
grep -A5 "TaskExecutor\|process_pending_tasks" tutors/*/run.py
```

### Проблема 3: Задачи не выполняются
**Симптом:** Статус задач всегда `pending`

**Причина:** scheduled_time в неправильном формате или таймзоне

**Решение:**
```bash
# Проверьте задачи
sqlite3 tutor_bot.db << 'EOF'
SELECT
    id,
    task_type,
    scheduled_time,
    datetime('now') as current_time,
    (scheduled_time <= datetime('now')) as should_execute
FROM scheduled_tasks
WHERE status='pending'
LIMIT 5;
EOF
```

---

## 📞 Поддержка

Если возникли проблемы:
1. Сделайте откат: `./restore_from_backup.sh`
2. Сохраните логи: `tar -czf logs_error.tar.gz tutors/*/logs/`
3. Проверьте `TESTING_PLAN.md` для детального анализа

---

**Удачи в тестировании! 🍀**
