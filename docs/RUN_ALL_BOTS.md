# Запуск всех ботов репетиторов

Этот документ описывает способы запуска всех ботов одновременно.

## Структура проекта

```
/root/TelegramBot/RebornTgBot/
├── bot_template/          # Общий код (handlers, keyboards, db_manager)
├── tutors/                # Папка с ботами репетиторов
│   ├── tutor_123456/     # Бот репетитора с ID 123456
│   │   ├── run.py        # Запуск бота
│   │   ├── config.py     # Конфигурация
│   │   ├── .env          # Переменные окружения
│   │   └── tutor_bot.db  # База данных
│   └── tutor_789012/     # Бот другого репетитора
│       └── ...
├── run_all_bots.py        # Скрипт для запуска всех ботов (Python)
├── run_all_bots_systemd.sh # Скрипт для управления через systemd
└── create_systemd_services.py # Создание systemd сервисов
```

## Вариант 1: Запуск через Python скрипт (для тестирования)

Скрипт `run_all_bots.py` запускает все боты в отдельных процессах и отслеживает их статус.

### Использование:

```bash
cd /root/TelegramBot/RebornTgBot
source venv/bin/activate
python3 run_all_bots.py
```

### Особенности:

- ✅ Автоматически находит все боты в папке `tutors/`
- ✅ Запускает каждый бот в отдельном процессе
- ✅ Отслеживает статус всех ботов
- ✅ Корректно завершает все процессы при нажатии Ctrl+C
- ✅ Показывает логи каждого бота

### Преимущества:

- Простота использования
- Хорошо для тестирования и разработки
- Не требует прав root

### Недостатки:

- Процессы завершаются при закрытии терминала
- Нет автоматического перезапуска при сбоях

## Вариант 2: Запуск через systemd (для production)

Рекомендуется для постоянной работы на сервере.

### Шаг 1: Создание systemd сервисов

```bash
cd /root/TelegramBot/RebornTgBot
python3 create_systemd_services.py
```

Скрипт автоматически:
- Найдет все боты в папке `tutors/`
- Создаст systemd сервис для каждого бота
- Настроит правильные пути и пользователя

### Шаг 2: Активация сервисов

```bash
# Перезагрузить systemd
sudo systemctl daemon-reload

# Включить автозапуск всех ботов
sudo systemctl enable tg-bot-*.service

# Запустить все боты
sudo systemctl start tg-bot-*.service
```

### Шаг 3: Управление через скрипт

```bash
# Запустить все боты
./run_all_bots_systemd.sh start

# Остановить все боты
./run_all_bots_systemd.sh stop

# Перезапустить все боты
./run_all_bots_systemd.sh restart

# Показать статус всех ботов
./run_all_bots_systemd.sh status
```

### Управление отдельным ботом:

```bash
# Статус
sudo systemctl status tg-bot-123456.service

# Запуск
sudo systemctl start tg-bot-123456.service

# Остановка
sudo systemctl stop tg-bot-123456.service

# Перезапуск
sudo systemctl restart tg-bot-123456.service

# Логи
sudo journalctl -u tg-bot-123456.service -f
```

### Преимущества:

- ✅ Автоматический запуск при перезагрузке сервера
- ✅ Автоматический перезапуск при сбоях
- ✅ Централизованное логирование через journalctl
- ✅ Управление через стандартные команды systemd

## Сравнение методов

| Характеристика | Python скрипт | systemd |
|----------------|---------------|---------|
| Автозапуск при перезагрузке | ❌ | ✅ |
| Автоперезапуск при сбое | ❌ | ✅ |
| Управление через стандартные команды | ❌ | ✅ |
| Логирование | stdout/stderr | journalctl |
| Простота использования | ✅ | ⚠️ |
| Для production | ❌ | ✅ |
| Для тестирования | ✅ | ⚠️ |

## Рекомендации

- **Для разработки/тестирования:** Используйте `run_all_bots.py`
- **Для production сервера:** Используйте systemd сервисы

## Устранение проблем

### Бот не запускается

1. Проверьте наличие файлов:
   ```bash
   ls -la tutors/tutor_*/run.py
   ls -la tutors/tutor_*/.env
   ```

2. Проверьте логи:
   ```bash
   # Для Python скрипта - смотрите вывод в терминале
   # Для systemd:
   sudo journalctl -u tg-bot-123456.service -n 50
   ```

3. Проверьте переменные окружения:
   ```bash
   cat tutors/tutor_123456/.env
   ```

### Ошибка "Module not found"

Убедитесь, что виртуальное окружение активировано и зависимости установлены:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Ошибка "Permission denied"

Проверьте права доступа к файлам:

```bash
chmod +x run_all_bots.py
chmod +x run_all_bots_systemd.sh
```

Для systemd проверьте пользователя в сервисе:

```bash
sudo systemctl edit tg-bot-123456.service
```

## Резервное копирование

Рекомендуется регулярно делать бэкап баз данных всех ботов:

```bash
#!/bin/bash
# backup_all_bots.sh

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

Добавьте в cron для автоматического бэкапа:

```bash
0 3 * * * /root/backup_all_bots.sh
```

