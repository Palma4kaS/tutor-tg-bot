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

## Безопасность

- Секреты хранятся вне репозитория через `.env` файлы.
- Для каждого репетитора используется изолированная конфигурация и отдельная база данных.
- Доступ репетитора ограничен Telegram ID.
- Процессы управляются через systemd на VPS.
- Логи доступны через `journalctl` для отладки и базового мониторинга.
- Чувствительные файлы (токены ботов, SQLite базы) исключены из Git.

## Стек

| Компонент | Технологии |
|-----------|------------|
| Бот | Python, aiogram 3, APScheduler, SQLite |
| Backend Mini App | FastAPI, aiosqlite |
| Frontend Mini App | React, TypeScript, Vite |

## Структура проекта

```
.
├── bot_template/
├── tutors/
├── miniapp/
├── deploy_bot.py
├── create_systemd_services.py
└── run_all_bots.py
```

## Быстрый старт

### 1. Клонировать и установить зависимости

```bash
git clone https://github.com/Palma4kaS/tutor-tg-bot.git
cd tutor-tg-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Создать бота для репетитора

```bash
python3 deploy_bot.py
```

## Mini App

### Backend
```bash
cd miniapp/backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd miniapp/frontend
npm install
npm run dev
```

## Документация

- [Установка на VPS](docs/INSTALL.md)
- [Запуск нескольких ботов](docs/RUN_ALL_BOTS.md)
- [Быстрый старт на VPS](docs/QUICK_START_VPS.md)
- [Зачем systemd](docs/WHY_SYSTEMD.md)
