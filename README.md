# Tutor Telegram Bot

Платформа для репетиторов на базе Telegram. Включает бота для управления учениками, занятиями и домашними заданиями, а также Telegram Mini App для учеников.

## Возможности

**Для репетитора (через бота):**
- Управление учениками: профили, расписание, история занятий
- Отметка оплаты и статуса занятия
- Домашние задания с прикреплением фото
- Просмотр должников и изменений профилей учеников
- Автоматические уведомления ученикам (за 3 часа до занятия, за 5 минут до конца)

**Для ученика (через Mini App):**
- Расписание предстоящих занятий
- Просмотр домашних заданий с фото
- История занятий и оплат
- Изменение профиля (имя, класс, направление — раз в неделю)

**Архитектура:**
- Multi-tenant: один деплой поддерживает несколько репетиторов, каждый со своим ботом и отдельной БД
- Автогенерация занятий по расписанию
- Деплой через systemd для стабильной работы на VPS

## Security considerations

- Secrets are stored outside the repository using `.env` files.
- Each tutor has isolated configuration and database storage.
- Tutor access is restricted by Telegram ID.
- Runtime processes are managed through systemd services on VPS.
- Logs can be inspected through `journalctl` for debugging and basic monitoring.
- Sensitive runtime files such as bot tokens and SQLite databases are excluded from Git.

## Стек

| Компонент | Технологии |
|-----------|------------|
| Бот | Python, aiogram 3, APScheduler, SQLite |
| Backend Mini App | FastAPI, aiosqlite |
| Frontend Mini App | React, TypeScript, Vite |

## Структура проекта

```
.
├── bot_template/          # Общий код бота (используется всеми репетиторами)
│   ├── app/               # Хэндлеры и клавиатуры
│   ├── database/          # Менеджер БД
│   ├── config.py          # Конфигурация
│   └── run.py             # Точка входа
├── tutors/                # Папки репетиторов (не в git)
│   └── tutor_<ID>/        # Данные конкретного репетитора
│       ├── .env           # Токен и ID
│       └── tutor_bot.db   # База данных
├── miniapp/
│   ├── backend/           # FastAPI backend
│   └── frontend/          # React frontend
├── deploy_bot.py          # Создание нового бота
├── create_systemd_services.py
└── run_all_bots.py
```

## Быстрый старт

### 1. Клонировать и установить зависимости

```bash
git clone https://github.com/Palma4kaS/tutor-rg-bot.git
cd tutor-rg-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Создать бота для репетитора

```bash
python3 deploy_bot.py
```

Скрипт запросит Telegram ID репетитора и токен бота (получить у [@BotFather](https://t.me/BotFather)).
Создаст папку `tutors/tutor_<ID>/` с `.env` и базой данных.

### 3. Запустить

**Для разработки:**
```bash
python3 run_all_bots.py
```

**На VPS через systemd:**
```bash
python3 create_systemd_services.py
sudo systemctl daemon-reload
sudo systemctl enable tg-bot-*.service
./run_all_bots_systemd.sh start
```

Управление:
```bash
./run_all_bots_systemd.sh status    # Статус всех ботов
./run_all_bots_systemd.sh restart   # Перезапустить все
sudo journalctl -u tg-bot-<ID> -f  # Логи конкретного бота
```

## Mini App

### Backend

```bash
cd miniapp/backend
cp bots_config.py.example bots_config.py
# Заполнить bots_config.py токенами ботов
cp .env.example .env
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd miniapp/frontend
cp .env.example .env
npm install
npm run dev
```

Подробнее: [miniapp/DEPLOY.md](miniapp/DEPLOY.md)

## Добавление нового репетитора

```bash
python3 deploy_bot.py
# Выбрать: создать нового бота
# Ввести Telegram ID и токен бота
```

После этого добавить токен в `miniapp/backend/bots_config.py`:
```bash
cd miniapp/backend
python3 add_bot.py
```

## Документация

- [Установка на VPS](docs/INSTALL.md)
- [Запуск нескольких ботов](docs/RUN_ALL_BOTS.md)
- [Быстрый старт на VPS](docs/QUICK_START_VPS.md)
- [Зачем systemd](docs/WHY_SYSTEMD.md)
