#!/bin/bash
# Скрипт для создания полного бэкапа перед обновлением

set -e  # Выход при ошибке

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$SCRIPT_DIR/backups/$(date +%Y%m%d_%H%M%S)"

echo "======================================"
echo "🔒 СОЗДАНИЕ БЭКАПА ПЕРЕД ОБНОВЛЕНИЕМ"
echo "======================================"
echo ""

# Создаем директорию для бэкапа
mkdir -p "$BACKUP_DIR"
echo "📁 Директория бэкапа: $BACKUP_DIR"
echo ""

# 1. Бэкап кода
echo "📦 Создание бэкапа кода..."
git_commit=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
echo "$git_commit" > "$BACKUP_DIR/git_commit.txt"
echo "   Текущий коммит: $git_commit"

# Сохраняем текущий статус
git status > "$BACKUP_DIR/git_status.txt" 2>&1 || echo "Git not available"
echo "   ✅ Git статус сохранен"
echo ""

# 2. Бэкап всех баз данных
echo "💾 Создание бэкапа баз данных..."
db_count=0

for tutor_dir in "$SCRIPT_DIR"/tutors/tutor_*; do
    if [ -d "$tutor_dir" ]; then
        tutor_name=$(basename "$tutor_dir")
        db_file="$tutor_dir/tutor_bot.db"

        if [ -f "$db_file" ]; then
            # Создаем поддиректорию для каждого бота
            mkdir -p "$BACKUP_DIR/$tutor_name"

            # Копируем БД
            cp "$db_file" "$BACKUP_DIR/$tutor_name/tutor_bot.db"

            # Копируем .env
            if [ -f "$tutor_dir/.env" ]; then
                cp "$tutor_dir/.env" "$BACKUP_DIR/$tutor_name/.env"
            fi

            # Копируем config.py
            if [ -f "$tutor_dir/config.py" ]; then
                cp "$tutor_dir/config.py" "$BACKUP_DIR/$tutor_name/config.py"
            fi

            # Получаем статистику БД
            db_size=$(du -h "$db_file" | cut -f1)
            students=$(sqlite3 "$db_file" "SELECT COUNT(*) FROM students" 2>/dev/null || echo "?")
            lessons=$(sqlite3 "$db_file" "SELECT COUNT(*) FROM lessons" 2>/dev/null || echo "?")

            echo "   ✅ $tutor_name"
            echo "      Размер: $db_size, Учеников: $students, Уроков: $lessons"

            db_count=$((db_count + 1))
        fi
    fi
done

if [ $db_count -eq 0 ]; then
    echo "   ⚠️  Базы данных не найдены"
else
    echo ""
    echo "   📊 Всего БД скопировано: $db_count"
fi
echo ""

# 3. Бэкап логов (если есть)
echo "📋 Создание бэкапа логов..."
if [ -d "$SCRIPT_DIR/logs" ]; then
    cp -r "$SCRIPT_DIR/logs" "$BACKUP_DIR/logs"
    echo "   ✅ Логи скопированы"
else
    echo "   ℹ️  Логов нет (это нормально для старой версии)"
fi
echo ""

# 4. Создаем манифест бэкапа
echo "📝 Создание манифеста..."
cat > "$BACKUP_DIR/MANIFEST.txt" << EOF
Бэкап RebornTgBot
Дата создания: $(date '+%Y-%m-%d %H:%M:%S')
Git коммит: $git_commit
Количество БД: $db_count

Содержимое:
$(find "$BACKUP_DIR" -type f -printf "  %P\n" | sort)

Инструкция по восстановлению:
  ./restore_from_backup.sh $(basename "$BACKUP_DIR")
EOF
echo "   ✅ Манифест создан"
echo ""

# 5. Создаем архив (опционально)
echo "🗜️  Создание архива..."
cd "$SCRIPT_DIR/backups"
tar -czf "$(basename "$BACKUP_DIR").tar.gz" "$(basename "$BACKUP_DIR")"
archive_size=$(du -h "$(basename "$BACKUP_DIR").tar.gz" | cut -f1)
echo "   ✅ Архив создан: $(basename "$BACKUP_DIR").tar.gz ($archive_size)"
echo ""

# Итог
echo "======================================"
echo "✅ БЭКАП ЗАВЕРШЕН УСПЕШНО"
echo "======================================"
echo ""
echo "📁 Расположение: $BACKUP_DIR"
echo "📦 Архив: $BACKUP_DIR.tar.gz"
echo ""
echo "Для восстановления используйте:"
echo "  ./restore_from_backup.sh $(basename "$BACKUP_DIR")"
echo ""
echo "Теперь можно безопасно обновлять боты."
echo ""
