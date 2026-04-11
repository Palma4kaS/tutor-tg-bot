#!/bin/bash

# Скрипт установки Telegram бота на VPS
# Использование: bash install.sh

set -e  # Остановка при ошибке

echo "🚀 Начинаем установку Telegram бота..."

# Проверка прав root
if [ "$EUID" -eq 0 ]; then 
   echo "⚠️  Не рекомендуется запускать от root. Создайте обычного пользователя."
   read -p "Продолжить? (y/n) " -n 1 -r
   echo
   if [[ ! $REPLY =~ ^[Yy]$ ]]; then
       exit 1
   fi
fi

# Определяем путь к проекту
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "📦 Обновление системы..."
sudo apt update
sudo apt upgrade -y

echo "🐍 Установка Python и зависимостей..."
sudo apt install -y python3 python3-pip python3-venv git

echo "📁 Создание виртуального окружения..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Виртуальное окружение создано"
else
    echo "✅ Виртуальное окружение уже существует"
fi

echo "🔧 Активация виртуального окружения и установка зависимостей..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "📝 Проверка .env файла..."
if [ ! -f "bot_template/.env" ]; then
    echo "⚠️  Файл .env не найден!"
    echo "Создайте файл bot_template/.env со следующим содержимым:"
    echo ""
    echo "BOT_TOKEN=ваш_токен_от_BotFather"
    echo "TUTOR_ID=ваш_telegram_id"
    echo "ADMIN_ID=ваш_telegram_id_или_0"
    echo ""
    read -p "Создать файл .env сейчас? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Введите BOT_TOKEN: " BOT_TOKEN
        read -p "Введите TUTOR_ID: " TUTOR_ID
        read -p "Введите ADMIN_ID (или оставьте пустым): " ADMIN_ID
        
        cat > bot_template/.env << EOF
BOT_TOKEN=$BOT_TOKEN
TUTOR_ID=$TUTOR_ID
ADMIN_ID=${ADMIN_ID:-0}
EOF
        echo "✅ Файл .env создан"
    else
        echo "❌ Необходимо создать .env файл вручную перед запуском"
        exit 1
    fi
else
    echo "✅ Файл .env найден"
fi

echo "🧪 Проверка установки..."
cd bot_template
python3 -c "import aiogram; import apscheduler; import aiosqlite; print('✅ Все модули установлены корректно')" || {
    echo "❌ Ошибка импорта модулей"
    exit 1
}

echo ""
echo "✅ Установка завершена!"
echo ""
echo "📋 Следующие шаги:"
echo "1. Проверьте файл bot_template/.env"
echo "2. Протестируйте запуск: cd bot_template && ../venv/bin/python3 run.py"
echo "3. Настройте systemd сервис (см. INSTALL.md)"
echo ""
echo "Для запуска бота:"
echo "  cd bot_template"
echo "  source ../venv/bin/activate"
echo "  python3 run.py"

