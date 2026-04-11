# 🧪 План тестирования перед обновлением на сервере

**Дата:** 2026-01-08
**Ветка:** main (после merge feature/task-scheduling-system)
**Критичность:** ВЫСОКАЯ (изменения затрагивают систему уведомлений)

---

## 📋 Основные изменения

### ✅ Что добавлено:
1. **Новая таблица БД:** `scheduled_tasks` для хранения задач
2. **Система задач:** `task_manager.py` + `task_executor.py`
3. **Логирование:** `logger.py` с ротацией файлов
4. **Индексы БД:** для ускорения запросов
5. **Автомиграция БД:** автоматическое добавление колонок

### ⚠️ Что изменилось:
- Уведомления теперь планируются в БД, а не через cron-проверки
- Добавлена retry-логика (3 попытки с интервалом 5 минут)
- Логи пишутся в файлы: `logs/bot.log` и `logs/error.log`

---

## 🔍 Анализ рисков

### 🟢 Низкий риск:
- ✅ Миграция БД безопасна (использует `IF NOT EXISTS`)
- ✅ Старые данные не затрагиваются
- ✅ Индексы создаются неинвазивно

### 🟡 Средний риск:
- ⚠️ Новая логика задач может не сработать с первого раза
- ⚠️ Возможны проблемы с таймзонами (Москва UTC+3)
- ⚠️ Циклические импорты между модулями

### 🔴 Высокий риск:
- ❌ Уведомления могут не отправляться (критично!)
- ❌ Автогенерация уроков может не работать
- ❌ Двойные уведомления (если старая и новая система работают одновременно)

---

## 🧪 План тестирования

### Этап 1: Проверка кода (статический анализ)

**1.1. Проверка синтаксиса Python**
```bash
cd /home/palma/RebornTgBot
source venv/bin/activate
python3 -m py_compile bot_template/database/task_manager.py
python3 -m py_compile bot_template/database/task_executor.py
python3 -m py_compile bot_template/utils/logger.py
```

**1.2. Проверка импортов**
```bash
python3 -c "from bot_template.database.task_manager import TaskManager; print('OK')"
python3 -c "from bot_template.database.task_executor import TaskExecutor; print('OK')"
python3 -c "from bot_template.utils.logger import get_logger; print('OK')"
```

**1.3. Проверка на циклические зависимости**
```bash
# Попробуйте импортировать run.py
python3 -c "import sys; sys.path.insert(0, 'tutors/tutor_910518469'); from bot_template.run import *; print('OK')"
```

---

### Этап 2: Тестирование БД (миграция)

**2.1. Создать копию продакшн БД**
```bash
# На сервере
cp tutors/tutor_910518469/tutor_bot.db tutors/tutor_910518469/tutor_bot.db.backup_20260108
```

**2.2. Запустить миграцию на тестовой копии**
```bash
# Локально или на сервере в тестовой папке
python3 << 'EOF'
import asyncio
import sys
sys.path.insert(0, 'tutors/tutor_910518469')
from bot_template.database.db_manager import DatabaseManager

async def test_migration():
    db = DatabaseManager('test_migration.db')
    await db.init_db()
    print("✅ Миграция успешна!")

    # Проверим, что таблица создана
    import aiosqlite
    async with aiosqlite.connect('test_migration.db') as conn:
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scheduled_tasks'")
        result = await cursor.fetchone()
        if result:
            print("✅ Таблица scheduled_tasks создана")
        else:
            print("❌ Таблица scheduled_tasks НЕ создана!")

        # Проверим индексы
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        indices = await cursor.fetchall()
        print(f"✅ Создано {len(indices)} индексов")
        for idx in indices:
            print(f"  - {idx[0]}")

asyncio.run(test_migration())
EOF
```

**2.3. Проверить структуру таблицы**
```bash
sqlite3 test_migration.db "PRAGMA table_info(scheduled_tasks);"
sqlite3 test_migration.db "SELECT name FROM sqlite_master WHERE type='index';"
```

---

### Этап 3: Локальное тестирование бота

**3.1. Создать тестового бота**
```bash
# Создайте тестовый токен в @BotFather
# Добавьте в .env:
# BOT_TOKEN=ваш_тестовый_токен
# TUTOR_ID=ваш_telegram_id

# Запустите бота локально
cd /home/palma/RebornTgBot/tutors/tutor_910518469
python3 run.py
```

**3.2. Проверить запуск и логи**
- ✅ Бот запустился без ошибок
- ✅ Создались файлы логов: `logs/bot.log`, `logs/error.log`
- ✅ В консоли нет критических ошибок
- ✅ APScheduler запустился

**3.3. Проверить систему логирования**
```bash
# Логи должны создаться
ls -lh logs/
cat logs/bot.log | tail -20
cat logs/error.log
```

---

### Этап 4: Тестирование системы задач

**4.1. Создать тестовое занятие на ближайшее время**
```bash
# Через бота:
# 1. Зарегистрируйтесь как ученик
# 2. Учитель создает занятие на +15 минут от текущего времени
```

**4.2. Проверить создание задач в БД**
```bash
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

**Ожидаемый результат:**
- 3 задачи для занятия:
  - `lesson_starting_notification` (за 3 часа)
  - `lesson_start_notification` (в момент начала)
  - `lesson_ending_notification` (за 5 минут до конца)

**4.3. Проверить выполнение задач**
- Дождитесь времени уведомления
- Проверьте, что уведомление пришло
- Проверьте статус задачи в БД:
```bash
sqlite3 tutors/tutor_910518469/tutor_bot.db "SELECT * FROM scheduled_tasks WHERE status='completed';"
```

**4.4. Тест retry-логики**
```bash
# Остановите бота
# Дождитесь времени задачи
# Запустите бота снова
# Проверьте, что задача выполнилась с retry
```

---

### Этап 5: Тестирование критичных функций

**5.1. Регистрация ученика**
- ✅ Команда `/start`
- ✅ Прохождение всех шагов регистрации
- ✅ Данные сохраняются в БД

**5.2. Создание расписания**
- ✅ Учитель создает регулярное расписание
- ✅ Автогенерация уроков работает
- ✅ Создаются задачи для уроков

**5.3. Уведомления**
- ✅ Уведомление за 3 часа (с кнопкой подтверждения)
- ✅ Уведомление за 5 минут до конца
- ✅ Уведомления приходят вовремя

**5.4. Домашние задания**
- ✅ Учитель назначает ДЗ с фото
- ✅ Ученик видит ДЗ с фото
- ✅ file_id сохраняется правильно

**5.5. Управление уроками**
- ✅ Отметка оплаты
- ✅ Отметка проведения
- ✅ Удаление урока (с флагом `is_manually_deleted`)
- ✅ Удаленный урок НЕ пересоздается

---

### Этап 6: Стресс-тест

**6.1. Создать много занятий**
```bash
# Создайте 10-20 занятий на разные даты
# Проверьте, что создались задачи для всех
```

**6.2. Проверить производительность БД**
```bash
sqlite3 tutors/tutor_910518469/tutor_bot.db << 'EOF'
EXPLAIN QUERY PLAN
SELECT * FROM lessons
WHERE student_id = 123 AND lesson_date > '2026-01-08'
ORDER BY lesson_date;
EOF
```

**Ожидается:** Использование индекса `idx_lessons_student_date`

---

### Этап 7: Проверка совместимости

**7.1. Работа с существующими данными**
- ✅ Старые уроки отображаются корректно
- ✅ Старые ученики работают без проблем
- ✅ История изменений сохранена

**7.2. Обратная совместимость**
- ✅ Уроки без `duration` (старые) работают с дефолтом 60 минут
- ✅ Старые форматы времени обрабатываются

---

## 🚨 Критерии провала теста

Если хотя бы одно из этих условий выполнено - НЕ обновляйте на сервере:

1. ❌ Бот не запускается (ошибки импорта, синтаксиса)
2. ❌ Миграция БД падает с ошибкой
3. ❌ Уведомления не отправляются
4. ❌ Автогенерация уроков не работает
5. ❌ Удаленные уроки пересоздаются
6. ❌ В логах много критических ошибок
7. ❌ Задачи не выполняются (status остается 'pending')

---

## 📦 Чеклист перед обновлением на сервере

### Подготовка:
- [ ] Все тесты пройдены успешно
- [ ] Локальное тестирование завершено
- [ ] Создан бэкап всех БД
- [ ] Создан бэкап старого кода
- [ ] Проверен план отката

### Обновление:
- [ ] Остановлены все боты: `./run_all_bots_systemd.sh stop`
- [ ] Обновлен код через `git pull` или `deploy_bot.py`
- [ ] Запущены боты: `./run_all_bots_systemd.sh start`
- [ ] Проверены логи: `./run_all_bots_systemd.sh status`

### Проверка после обновления:
- [ ] Все боты запущены (systemctl status)
- [ ] Нет ошибок в логах
- [ ] Тестовое уведомление отправилось
- [ ] Автогенерация работает
- [ ] Ученики могут пользоваться ботом

---

## 🔙 План отката (Rollback Plan)

Если что-то пошло не так:

### Быстрый откат (5 минут):

```bash
# 1. Остановить все боты
./run_all_bots_systemd.sh stop

# 2. Откатить код на предыдущую версию
git checkout e7efa0a  # Последний коммит до merge

# 3. Восстановить БД из бэкапа (если нужно)
cp tutors/tutor_910518469/tutor_bot.db.backup_20260108 tutors/tutor_910518469/tutor_bot.db

# 4. Запустить боты
./run_all_bots_systemd.sh start

# 5. Проверить статус
./run_all_bots_systemd.sh status
```

### Детальный откат:

```bash
# Если нужно сохранить новые данные:
# 1. Экспортировать новые уроки/учеников
# 2. Откатить код
# 3. Импортировать данные обратно

# Скрипт для экспорта будет создан при необходимости
```

---

## 📊 Мониторинг после обновления

### Первые 24 часа:
- Каждый час проверять логи на ошибки
- Отслеживать доставку уведомлений
- Проверять статус задач в БД

### Первая неделя:
- Ежедневно проверять логи
- Мониторить производительность БД
- Собирать feedback от репетиторов

---

## 📞 Контакты при проблемах

Если тесты провалились или возникли вопросы:
1. Проверьте логи: `cat logs/error.log`
2. Проверьте статус задач: `sqlite3 tutor_bot.db "SELECT * FROM scheduled_tasks WHERE status='failed';"`
3. Сделайте откат по плану выше

---

**Успехов в тестировании! 🚀**
