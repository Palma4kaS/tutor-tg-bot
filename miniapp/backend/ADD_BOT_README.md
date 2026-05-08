# Добавление нового бота в систему

Этот файл содержит инструкции по добавлению нового учителя и его бота в систему miniapp.

## Автоматический способ (рекомендуется)

Используйте скрипт `add_bot.py`:

```bash
cd miniapp/backend
python add_bot.py
```

Скрипт запросит:
1. **Bot Token** - токен бота от BotFather
2. **Название папки** - автоматически определяется как `tutor_{TUTOR_ID}`
3. **Описание** (опционально) - комментарий для конфига

### Что делает скрипт:
- ✅ Проверяет формат токена
- ✅ Получает информацию о боте через API
- ✅ Проверяет наличие папки и БД
- ✅ Создает папку если нужно
- ✅ Автоматически добавляет бота в `config.py`
- ✅ Показывает инструкции по деплою

### Пример использования:

```
$ python add_bot.py

======================================================================
🤖 ДОБАВЛЕНИЕ НОВОГО БОТА В MINIAPP
======================================================================

Шаг 1: Введите токен бота
Формат: 123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Bot Token: 1234567890:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
✅ Формат токена корректен

Получаем информацию о боте...
✅ Бот найден:
   ID: 1234567890
   Username: @new_tutor_bot
   Name: New Tutor Bot

Шаг 2: Папка репетитора
Рекомендуемое название: tutor_1234567890
Введите название папки [tutor_1234567890]:
✅ Папка найдена: /path/to/tutors/tutor_1234567890
✅ База данных найдена: /path/to/tutors/tutor_1234567890/tutor_bot.db

Шаг 3: Описание (опционально)
Описание бота (например, 'Бот Иванова'): Бот Петрова

Добавить бота в конфигурацию? (yes/no): yes

✅ Бот успешно добавлен в config.py!
```

---

## Ручной способ

### Шаг 1: Подготовка папки

Создайте папку для нового репетитора:

```bash
mkdir -p tutors/tutor_{TUTOR_ID}
```

Скопируйте в неё:
- `tutor_bot.db` - база данных бота
- `run.py` - основной скрипт бота (опционально)
- `config.py` - конфиг бота (опционально)
- `.env` - переменные окружения бота (опционально)

### Шаг 2: Добавление в конфигурацию

Откройте `miniapp/backend/config.py` и добавьте новую запись в `BOTS_CONFIG`:

```python
BOTS_CONFIG = {
    '1234567890:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx': 'tutor_123456789',  # Первый бот
    '9876543210:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx': 'tutor_987654321',  # Второй бот
    'НОВЫЙ_ТОКЕН_БОТА': 'tutor_НОВЫЙ_ID',  # Описание
}
```

### Шаг 3: Коммит и деплой

```bash
# Добавить и закоммитить изменения
git add miniapp/backend/config.py
git commit -m "Add bot for tutor_НОВЫЙ_ID"

# Отправить на сервер
git push origin miniapp

# На сервере
cd ~/TelegramBot/RebornTgBot
git pull origin miniapp
sudo systemctl restart miniapp-api

# Проверить логи
sudo journalctl -u miniapp-api -n 30 -f
```

---

## Проверка работы

### 1. Проверьте статус сервиса

```bash
sudo systemctl status miniapp-api
```

Должно быть `active (running)`.

### 2. Проверьте логи

```bash
sudo journalctl -u miniapp-api -n 50 --no-pager
```

При старте должно быть:
```
INFO:     Started server process [PID]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### 3. Откройте miniapp в боте

В Telegram откройте нового бота и запустите miniapp. В логах должно появиться:

```
INFO: Auth attempt - initData present: True
INFO: Successfully validated with bot for tutor: tutor_НОВЫЙ_ID
INFO: User authenticated successfully: user_id=..., username=..., tutor=tutor_НОВЫЙ_ID
```

---

## Устранение проблем

### Ошибка: "Failed to validate with any bot"

**Причина:** initData не подходит ни к одному токену в `BOTS_CONFIG`.

**Решение:**
1. Проверьте, что токен в `config.py` совпадает с токеном бота
2. Убедитесь, что miniapp открывается именно в этом боте
3. Перезапустите сервис после изменений в конфиге

### Ошибка: "Student not found"

**Причина:** База данных не содержит этого пользователя.

**Решение:**
1. Убедитесь, что БД скопирована правильно
2. Проверьте путь к БД: `tutors/tutor_ID/tutor_bot.db`
3. Убедитесь, что пользователь есть в таблице `students`

### 404 ошибки на endpoints

**Причина:** Сервис использует старую версию кода.

**Решение:**
```bash
cd ~/TelegramBot/RebornTgBot
git pull origin miniapp
sudo systemctl restart miniapp-api
```

---

## Дополнительная информация

### Структура папки репетитора

```
tutors/
└── tutor_1234567890/
    ├── tutor_bot.db       # База данных (обязательно)
    ├── run.py             # Основной бот (опционально)
    ├── config.py          # Конфиг бота (опционально)
    ├── .env               # Env переменные (опционально)
    └── logs/              # Логи бота (опционально)
```

### Переменные окружения бота (.env)

```env
BOT_TOKEN=1234567890:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TUTOR_ID=1234567890
ADMIN_ID=910518469
TUTOR_FOLDER=tutor_1234567890
```

### Настройка miniapp в BotFather

1. Откройте [@BotFather](https://t.me/BotFather)
2. `/mybots` → выберите бота
3. `Bot Settings` → `Menu Button`
4. `Configure menu button` или `Edit menu button URL`
5. URL: `https://ваш-домен.com/miniapp/` (или путь к вашему фронтенду)
