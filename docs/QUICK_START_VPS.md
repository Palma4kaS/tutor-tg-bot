# Быстрый старт на VPS

Краткая инструкция для запуска всех ботов на вашем VPS.

## Ваш путь на VPS

```
/root/TelegramBot/RebornTgBot
```

## Быстрая установка

```bash
# 1. Перейти в директорию проекта
cd /root/TelegramBot/RebornTgBot

# 2. Установить зависимости (если еще не установлены)
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# 3. Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# 4. Установить зависимости
pip install --upgrade pip
pip install -r requirements.txt
```

## Запуск всех ботов

### Вариант 1: Простой запуск (для тестирования)

```bash
cd /root/TelegramBot/RebornTgBot
source venv/bin/activate
python3 run_all_bots.py
```

### Вариант 2: Production запуск через systemd

```bash
# 1. Создать systemd сервисы для всех ботов
cd /root/TelegramBot/RebornTgBot
python3 create_systemd_services.py

# 2. Активировать и запустить
sudo systemctl daemon-reload
sudo systemctl enable tg-bot-*.service
sudo systemctl start tg-bot-*.service

# 3. Управление через скрипт
./run_all_bots_systemd.sh start    # Запустить все
./run_all_bots_systemd.sh status   # Статус
./run_all_bots_systemd.sh stop     # Остановить все
```

## Создание нового бота

```bash
cd /root/TelegramBot/RebornTgBot
python3 deploy_bot.py
```

## Полезные команды

### Проверка статуса всех ботов
```bash
./run_all_bots_systemd.sh status
```

### Логи конкретного бота
```bash
sudo journalctl -u tg-bot-123456.service -f
```

### Перезапуск всех ботов
```bash
./run_all_bots_systemd.sh restart
```

### Остановка всех ботов
```bash
./run_all_bots_systemd.sh stop
```

## Структура проекта

```
/root/TelegramBot/RebornTgBot/
├── bot_template/          # Общий код
├── tutors/                # Боты репетиторов
│   ├── tutor_123456/     # Бот репетитора
│   └── tutor_789012/     # Другой бот
├── venv/                  # Виртуальное окружение
├── run_all_bots.py        # Запуск всех ботов
└── deploy_bot.py          # Создание нового бота
```

## Резервное копирование

Создайте скрипт для бэкапа всех баз данных:

```bash
nano /root/backup_all_bots.sh
```

Добавьте:

```bash
#!/bin/bash
BACKUP_DIR="/root/backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

cd /root/TelegramBot/RebornTgBot

for tutor_dir in tutors/tutor_*; do
    tutor_id=$(basename "$tutor_dir" | sed 's/tutor_//')
    db_file="$tutor_dir/tutor_bot.db"
    
    if [ -f "$db_file" ]; then
        cp "$db_file" "$BACKUP_DIR/tutor_${tutor_id}.db"
        echo "✅ Бэкап бота $tutor_id"
    fi
done

echo "✅ Все боты скопированы в $BACKUP_DIR"
```

Сделайте исполняемым:

```bash
chmod +x /root/backup_all_bots.sh
```

Добавьте в cron (ежедневно в 3:00):

```bash
crontab -e
# Добавьте строку:
0 3 * * * /root/backup_all_bots.sh
```

## Решение проблем

### Бот не запускается
```bash
# Проверьте логи
sudo journalctl -u tg-bot-123456.service -n 50

# Проверьте .env файл
cat /root/TelegramBot/RebornTgBot/tutors/tutor_123456/.env
```

### Ошибка импорта модулей
```bash
cd /root/TelegramBot/RebornTgBot
source venv/bin/activate
pip install -r requirements.txt --force-reinstall
```

### Все боты не запускаются
```bash
# Проверьте, что все боты созданы
ls -la /root/TelegramBot/RebornTgBot/tutors/

# Проверьте, что у всех есть .env и run.py
for dir in /root/TelegramBot/RebornTgBot/tutors/tutor_*; do
    echo "Проверяю: $dir"
    ls -la "$dir/.env" "$dir/run.py" 2>/dev/null || echo "❌ Файлы не найдены"
done
```

