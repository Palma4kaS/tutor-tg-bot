#!/bin/bash
# Скрипт для восстановления из бэкапа

set -e  # Выход при ошибке

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Проверка аргументов
if [ $# -eq 0 ]; then
    echo "❌ Ошибка: не указан бэкап для восстановления"
    echo ""
    echo "Использование: $0 <backup_name>"
    echo ""
    echo "Доступные бэкапы:"
    ls -1 "$SCRIPT_DIR/backups" | grep -v ".tar.gz" | sed 's/^/  /'
    exit 1
fi

BACKUP_NAME="$1"
BACKUP_DIR="$SCRIPT_DIR/backups/$BACKUP_NAME"

# Проверка существования бэкапа
if [ ! -d "$BACKUP_DIR" ]; then
    # Может быть это архив?
    if [ -f "$SCRIPT_DIR/backups/$BACKUP_NAME.tar.gz" ]; then
        echo "📦 Распаковка архива..."
        cd "$SCRIPT_DIR/backups"
        tar -xzf "$BACKUP_NAME.tar.gz"
        echo "   ✅ Архив распакован"
    else
        echo "❌ Ошибка: бэкап '$BACKUP_NAME' не найден"
        exit 1
    fi
fi

echo "======================================"
echo "🔄 ВОССТАНОВЛЕНИЕ ИЗ БЭКАПА"
echo "======================================"
echo ""
echo "⚠️  ВНИМАНИЕ: Это действие перезапишет текущие данные!"
echo ""

# Показываем информацию о бэкапе
if [ -f "$BACKUP_DIR/MANIFEST.txt" ]; then
    cat "$BACKUP_DIR/MANIFEST.txt"
    echo ""
fi

# Подтверждение
read -p "Продолжить восстановление? [y/N]: " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Восстановление отменено"
    exit 1
fi

echo ""
echo "🛑 Остановка ботов..."
if [ -f "$SCRIPT_DIR/run_all_bots_systemd.sh" ]; then
    "$SCRIPT_DIR/run_all_bots_systemd.sh" stop 2>/dev/null || true
    echo "   ✅ Боты остановлены"
else
    echo "   ⚠️  Скрипт остановки не найден, остановите боты вручную"
    read -p "Боты остановлены? [y/N]: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
echo ""

# Восстановление кода
echo "🔄 Восстановление кода..."
if [ -f "$BACKUP_DIR/git_commit.txt" ]; then
    git_commit=$(cat "$BACKUP_DIR/git_commit.txt")
    echo "   Восстановление коммита: $git_commit"

    if git rev-parse --verify "$git_commit" >/dev/null 2>&1; then
        git checkout "$git_commit"
        echo "   ✅ Код восстановлен"
    else
        echo "   ⚠️  Коммит не найден в репозитории"
        echo "   Код останется в текущем состоянии"
    fi
else
    echo "   ⚠️  Информация о коммите не найдена"
fi
echo ""

# Восстановление БД
echo "💾 Восстановление баз данных..."
db_count=0

for backup_tutor_dir in "$BACKUP_DIR"/tutor_*; do
    if [ -d "$backup_tutor_dir" ]; then
        tutor_name=$(basename "$backup_tutor_dir")
        target_dir="$SCRIPT_DIR/tutors/$tutor_name"

        # Создаем директорию если не существует
        mkdir -p "$target_dir"

        # Восстанавливаем БД
        if [ -f "$backup_tutor_dir/tutor_bot.db" ]; then
            cp "$backup_tutor_dir/tutor_bot.db" "$target_dir/tutor_bot.db"
            echo "   ✅ $tutor_name: БД восстановлена"
            db_count=$((db_count + 1))
        fi

        # Восстанавливаем .env
        if [ -f "$backup_tutor_dir/.env" ]; then
            cp "$backup_tutor_dir/.env" "$target_dir/.env"
            echo "   ✅ $tutor_name: .env восстановлен"
        fi

        # Восстанавливаем config.py
        if [ -f "$backup_tutor_dir/config.py" ]; then
            cp "$backup_tutor_dir/config.py" "$target_dir/config.py"
            echo "   ✅ $tutor_name: config.py восстановлен"
        fi
    fi
done

echo ""
echo "   📊 Всего БД восстановлено: $db_count"
echo ""

# Восстановление логов
echo "📋 Восстановление логов..."
if [ -d "$BACKUP_DIR/logs" ]; then
    rm -rf "$SCRIPT_DIR/logs"
    cp -r "$BACKUP_DIR/logs" "$SCRIPT_DIR/logs"
    echo "   ✅ Логи восстановлены"
else
    echo "   ℹ️  Логов в бэкапе нет"
fi
echo ""

# Запуск ботов
echo "🚀 Запуск ботов..."
read -p "Запустить боты сейчас? [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "$SCRIPT_DIR/run_all_bots_systemd.sh" ]; then
        "$SCRIPT_DIR/run_all_bots_systemd.sh" start
        echo "   ✅ Боты запущены"
        echo ""
        sleep 2
        "$SCRIPT_DIR/run_all_bots_systemd.sh" status
    else
        echo "   ⚠️  Скрипт запуска не найден, запустите боты вручную"
    fi
fi

echo ""
echo "======================================"
echo "✅ ВОССТАНОВЛЕНИЕ ЗАВЕРШЕНО"
echo "======================================"
echo ""
