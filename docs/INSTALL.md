# Инструкция по установке Telegram бота на VPS

## Шаг 1: Обновление системы

```bash
sudo apt update
sudo apt upgrade -y
```

## Шаг 2: Установка Python и необходимых пакетов

```bash
sudo apt install -y python3 python3-pip python3-venv git
```

## Шаг 3: Переход в директорию проекта

```bash
cd /root/TelegramBot/RebornTgBot
```

**Важно:** Если проект еще не загружен, загрузите его в директорию `/root/TelegramBot/RebornTgBot`

## Шаг 4: Создание виртуального окружения

```bash
python3 -m venv venv
source venv/bin/activate
```

## Шаг 5: Установка зависимостей

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Шаг 6: Настройка переменных окружения

Создайте файл `.env` в папке `bot_template`:

```bash
cd /root/TelegramBot/RebornTgBot/bot_template
nano .env
```

Добавьте в файл следующие строки:

```
BOT_TOKEN=ваш_токен_от_BotFather
TUTOR_ID=ваш_telegram_id
ADMIN_ID=ваш_telegram_id_или_0
```

**Как получить:**
- `BOT_TOKEN`: создайте бота через [@BotFather](https://t.me/BotFather) в Telegram
- `TUTOR_ID`: ваш Telegram ID (можно узнать через [@userinfobot](https://t.me/userinfobot))

Сохраните файл: `Ctrl+O`, `Enter`, `Ctrl+X`

## Шаг 7: Проверка запуска

Запустите бота вручную для проверки:

```bash
cd /root/TelegramBot/RebornTgBot
source venv/bin/activate
cd bot_template
python3 run.py
```

Если всё работает, остановите бота: `Ctrl+C`

## Шаг 8: Настройка автозапуска через systemd

Создайте файл сервиса:

```bash
sudo nano /etc/systemd/system/tg-bot.service
```

Добавьте следующее содержимое:

```ini
[Unit]
Description=Telegram Bot Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/TelegramBot/RebornTgBot/bot_template
Environment="PATH=/root/TelegramBot/RebornTgBot/venv/bin"
ExecStart=/root/TelegramBot/RebornTgBot/venv/bin/python3 /root/TelegramBot/RebornTgBot/bot_template/run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Примечание:** Для вашей структуры с несколькими ботами используйте `create_systemd_services.py` для автоматического создания сервисов

Активируйте и запустите сервис:

```bash
sudo systemctl daemon-reload
sudo systemctl enable tg-bot
sudo systemctl start tg-bot
```

## Шаг 9: Проверка работы

Проверьте статус сервиса:

```bash
sudo systemctl status tg-bot
```

Просмотр логов:

```bash
sudo journalctl -u tg-bot -f
```

## Полезные команды

- **Остановить бота:** `sudo systemctl stop tg-bot`
- **Запустить бота:** `sudo systemctl start tg-bot`
- **Перезапустить бота:** `sudo systemctl restart tg-bot`
- **Посмотреть логи:** `sudo journalctl -u tg-bot -n 50`
- **Следить за логами:** `sudo journalctl -u tg-bot -f`

## Резервное копирование базы данных

Создайте скрипт для бэкапа:

```bash
nano /root/backup_db.sh
```

Добавьте:

```bash
#!/bin/bash
BACKUP_DIR="/root/backups"
mkdir -p $BACKUP_DIR
cp /root/TelegramBot/RebornTgBot/bot_template/tutor_bot.db $BACKUP_DIR/tutor_bot_$(date +%Y%m%d_%H%M%S).db
# Удаляем старые бэкапы (старше 7 дней)
find $BACKUP_DIR -name "tutor_bot_*.db" -mtime +7 -delete
```

Сделайте исполняемым:

```bash
chmod +x ~/backup_db.sh
```

Добавьте в cron (ежедневный бэкап в 3:00):

```bash
crontab -e
```

Добавьте строку:

```
0 3 * * * /root/backup_db.sh
```

## Решение проблем

### Бот не запускается
1. Проверьте логи: `sudo journalctl -u tg-bot -n 100`
2. Проверьте `.env` файл на наличие всех переменных
3. Проверьте права доступа к файлам

### Ошибка импорта модулей
```bash
source venv/bin/activate
pip install -r requirements.txt --force-reinstall
```

### Ошибка доступа к базе данных
```bash
sudo chown root:root /root/TelegramBot/RebornTgBot/bot_template/tutor_bot.db
```

