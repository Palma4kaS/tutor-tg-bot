# Полная сводка проекта RebornTgBot

## Дата создания документа: 2025-01-27

## Структура проекта

```
/root/TelegramBot/RebornTgBot/
├── bot_template/              # Общий код для всех ботов
│   ├── app/
│   │   ├── handlers.py        # Все обработчики команд и callback'ов (большой файл)
│   │   └── keyboards.py       # Все клавиатуры (inline и reply)
│   ├── database/
│   │   └── db_manager.py      # Менеджер базы данных
│   ├── config.py              # Конфигурация (цены, токены)
│   └── run.py                 # Точка входа бота
├── tutors/                     # Папка с индивидуальными ботами
│   ├── tutor_<ID>/            # Бот конкретного репетитора
│   │   ├── run.py            # Копия bot_template/run.py
│   │   ├── config.py         # Копия bot_template/config.py
│   │   ├── .env              # Переменные окружения (BOT_TOKEN, TUTOR_ID)
│   │   └── tutor_bot.db      # База данных бота
├── venv/                      # Виртуальное окружение Python
├── deploy_bot.py              # Скрипт создания нового бота
├── run_all_bots.py            # Запуск всех ботов одновременно
├── run_all_bots_systemd.sh   # Управление ботами через systemd
├── create_systemd_services.py # Создание systemd сервисов
├── requirements.txt           # Зависимости Python
└── *.md                       # Документация
```

## Основные компоненты

### 1. deploy_bot.py
- Создает нового бота для репетитора
- Копирует `config.py` и `run.py` в `tutors/tutor_<ID>/`
- Создает `.env` с токеном и ID
- Сохраняет существующую БД при перезаписи

### 2. bot_template/app/handlers.py
Основные обработчики:
- Регистрация учеников
- Управление профилем (изменение имени, класса, направления)
- Расписание занятий
- Управление оплатой
- Домашние задания (с фото)
- История занятий
- Статистика учеников
- Изменения профилей учеников (за неделю)
- Админ-панель учителя

**Ключевые функции:**
- `format_lesson_time(lesson_time: str, duration: int = 60) -> str` - форматирование времени занятия
- `show_student_card_internal()` - отображение профиля ученика
- `show_my_homework()` - список ДЗ для ученика
- `show_student_homework_detail()` - детали ДЗ с фото
- `toggle_lesson_status()` - переключение статуса занятия (проведено/не проведено)

### 3. bot_template/app/keyboards.py
Клавиатуры:
- `main` - главная клавиатура для учеников
- `admin_main` - панель учителя (с кнопкой "📝 Изменения учеников")
- `student_changes_list_keyboard()` - список учеников с изменениями
- `student_changes_details_keyboard()` - детали изменений ученика
- `student_homework_list_keyboard()` - список ДЗ для ученика
- `lesson_payment_keyboard()` - управление оплатой и статусом занятия
- И многие другие...

### 4. bot_template/database/db_manager.py
Менеджер базы данных:

**Таблицы:**
- `students` - информация об учениках
- `lessons` - занятия (с полями: homework, homework_photo_file_id, payment_status, status, duration)
- `schedules` - расписание (шаблоны для генерации занятий)
- `student_changes_history` - история изменений профилей учеников

**Ключевые методы:**
- `can_change_parameter(user_id, change_type)` - проверка ограничения "один раз в неделю"
- `update_student_name/grade/subject()` - обновление с сохранением истории
- `get_student_changes_last_week()` - изменения за неделю
- `get_student_changes(student_id, days)` - изменения конкретного ученика
- `update_lesson_status(lesson_id, status)` - обновление статуса занятия
- `update_lesson_homework()` - сохранение ДЗ с фото (file_id)

### 5. bot_template/run.py
- Точка входа бота
- Планировщик задач (APScheduler):
  - Автогенерация занятий (каждый день в 00:30 и каждые 6 часов)
  - Уведомления за 5 минут до окончания занятия
  - Уведомления за 3 часа до начала (с кнопкой подтверждения)
  - Уведомления за 24 часа (временно отключено)
  - Проверка неподтвержденных занятий

### 6. bot_template/config.py
Настройки:
- `BOT_TOKEN` - токен бота
- `TUTOR_ID` - ID репетитора
- `ADMIN_ID` - ID администратора
- Цены: `ONLINE`, `OFFLINE`, `PROFIL`, `CLASS_9`, `CLASS_10_11`

## Функциональность

### Для учеников:
1. Регистрация (имя, класс, направление)
2. Просмотр занятий (предстоящие, история)
3. Просмотр ДЗ (краткий список, детали с фото)
4. Изменение профиля (имя, класс, направление - раз в неделю)
5. Уведомления о занятиях

### Для учителя:
1. Панель управления:
   - Расписание
   - Список учеников
   - Должники
   - Новые ученики
   - Изменения учеников (за неделю)
   - Настройки

2. Управление учениками:
   - Просмотр профиля
   - Редактирование профиля
   - Управление расписанием
   - История занятий
   - Управление оплатой
   - Домашние задания (с фото)

3. Управление занятиями:
   - Отметка оплаты
   - Отметка проведения (проведено/не проведено)
   - Удаление занятия
   - Добавление ДЗ (текст + фото)

## База данных

### Таблица students
- `user_id` (PRIMARY KEY)
- `name`, `username`, `phone`, `grade`, `subject`
- `registration_date`
- `last_name_change_date` - дата последнего изменения имени
- `last_grade_change_date` - дата последнего изменения класса
- `last_subject_change_date` - дата последнего изменения направления
- `viewed_by_teacher` - флаг просмотра учителем

### Таблица lessons
- `id` (PRIMARY KEY AUTOINCREMENT)
- `student_id`, `lesson_date`, `lesson_time`
- `subject`, `lesson_format`, `price`, `duration`
- `status` (scheduled/completed/cancelled)
- `payment_status` (paid/unpaid/pending)
- `homework`, `homework_status`, `homework_photo_file_id`
- `confirmation_status`, `confirmation_sent_at`
- `schedule_id`, `is_rescheduled`, `original_date`, `notes`

### Таблица schedules
- `id` (PRIMARY KEY AUTOINCREMENT)
- `student_id`, `weekday`, `time`
- `lesson_format`, `price`, `duration`, `subject`
- `is_active`, `created_at`

### Таблица student_changes_history
- `id` (PRIMARY KEY AUTOINCREMENT)
- `student_id`, `change_type` (name/grade/subject)
- `old_value`, `new_value`
- `change_date`, `changed_by` (student/teacher)

## Команды для управления

### Создание нового бота
```bash
cd /root/TelegramBot/RebornTgBot
python3 deploy_bot.py
# Выбрать: 1
# Ввести ID репетитора и токен
```

### Запуск всех ботов (тестирование)
```bash
cd /root/TelegramBot/RebornTgBot
source venv/bin/activate
python3 run_all_bots.py
```

### Запуск через systemd
```bash
# 1. Создать сервисы
python3 create_systemd_services.py

# 2. Активировать
sudo systemctl daemon-reload
sudo systemctl enable tg-bot-*.service
sudo systemctl start tg-bot-*.service

# 3. Управление
./run_all_bots_systemd.sh start    # Запустить все
./run_all_bots_systemd.sh stop     # Остановить все
./run_all_bots_systemd.sh restart  # Перезапустить все
./run_all_bots_systemd.sh status   # Статус всех
```

### Управление одним ботом
```bash
# Остановить
sudo systemctl stop tg-bot-<ID>.service

# Запустить
sudo systemctl start tg-bot-<ID>.service

# Перезапустить
sudo systemctl restart tg-bot-<ID>.service

# Статус
sudo systemctl status tg-bot-<ID>.service

# Логи
sudo journalctl -u tg-bot-<ID>.service -f
```

## Важные особенности

### Ограничение изменений профиля
- Ученик может менять каждый параметр (имя, класс, направление) только один раз в неделю
- Проверка через `can_change_parameter()`
- Информация отображается в профиле: "ℹ️ Каждый параметр можно менять один раз в неделю"

### История изменений
- Все изменения сохраняются в `student_changes_history`
- Учитель может просмотреть изменения за последнюю неделю
- Формат: "Имя: Старое имя -> Новое имя"

### Домашние задания с фото
- Процесс добавления:
  1. Учитель вводит текст ДЗ
  2. Бот спрашивает "Прикрепить фото?"
  3. Если "Да" - учитель отправляет фото
  4. Сохраняется `file_id` в БД
- При редактировании: можно оставить старое фото, заменить или удалить

### Статус занятий
- `scheduled` - запланировано
- `completed` - проведено
- `cancelled` - отменено
- Кнопка "Отметить проведенным/не проведенным" переключает статус

### Форматирование времени
- Функция `format_lesson_time()` возвращает "HH:MM-HH:MM(duration)"
- Используется во всех местах отображения занятий

## Файлы документации

- `INSTALL.md` - полная инструкция по установке
- `RUN_ALL_BOTS.md` - запуск всех ботов
- `QUICK_START_VPS.md` - быстрый старт на VPS
- `WHY_SYSTEMD.md` - зачем нужен systemd
- `README.md` - краткое описание

## Зависимости (requirements.txt)

```
aiogram==3.22.0
python-dotenv==1.1.1
apscheduler==3.10.4
aiosqlite==0.21.0
```

## Пути на VPS

- Проект: `/root/TelegramBot/RebornTgBot`
- Бэкапы: `/root/backups`
- Виртуальное окружение: `/root/TelegramBot/RebornTgBot/venv`

## Планировщик задач

- **Автогенерация занятий**: ежедневно в 00:30 и каждые 6 часов
- **Уведомления за 5 минут до окончания**: каждую минуту
- **Уведомления за 3 часа до начала**: каждые 15 минут
- **Уведомления за 24 часа**: отключено (закомментировано)
- **Проверка неподтвержденных**: каждый час

## Последние изменения

1. Добавлена функция форматирования времени занятий
2. Изменена кнопка при удалении занятия ("Вернуться в историю ученика")
3. Добавлена функция "Изменения учеников" в панели учителя
4. Ограничение изменений профиля (раз в неделю)
5. Рефакторинг отображения профиля ученика
6. Добавлена возможность прикреплять фото к ДЗ
7. Изменен интерфейс ДЗ для ученика (краткий список + детали)
8. Добавлена кнопка переключения статуса занятия
9. Временно отключены уведомления за 24 часа
10. Исправлена ошибка с путем в run_all_bots.py

## Примечания

- Общий код находится в `bot_template/`
- Каждый бот имеет свою БД и настройки в `tutors/tutor_<ID>/`
- При создании нового бота через `deploy_bot.py` копируются только `config.py` и `run.py`
- `handlers.py`, `keyboards.py`, `db_manager.py` используются из `bot_template/` (общий код)

---

**Дата создания документа:** 2025-01-27
**Версия проекта:** Актуальная (после всех изменений)

