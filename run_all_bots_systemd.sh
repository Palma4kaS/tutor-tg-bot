#!/bin/bash
# Скрипт для запуска всех ботов через systemd
# Использование: ./run_all_bots_systemd.sh [start|stop|restart|status]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_PYTHON="$SCRIPT_DIR/venv/bin/python3"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ Виртуальное окружение не найдено!"
    echo "💡 Выполните: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

find_all_bots() {
    if [ ! -d "tutors" ]; then
        return
    fi
    
    for tutor_dir in tutors/tutor_*; do
        if [ -d "$tutor_dir" ] && [ -f "$tutor_dir/run.py" ] && [ -f "$tutor_dir/.env" ]; then
            tutor_id=$(basename "$tutor_dir" | sed 's/tutor_//')
            echo "$tutor_id|$tutor_dir"
        fi
    done
}

case "$1" in
    start)
        echo "🚀 Запуск всех ботов..."
        bots=$(find_all_bots)
        if [ -z "$bots" ]; then
            echo "❌ Боты не найдены в папке tutors/"
            exit 1
        fi
        
        count=0
        while IFS='|' read -r tutor_id tutor_dir; do
            if systemctl is-active --quiet "tg-bot-${tutor_id}.service" 2>/dev/null; then
                echo "⚠️  Бот $tutor_id уже запущен"
            else
                echo "▶️  Запускаю бота $tutor_id..."
                sudo systemctl start "tg-bot-${tutor_id}.service"
                ((count++))
            fi
        done <<< "$bots"
        
        echo "✅ Запущено ботов: $count"
        ;;
    
    stop)
        echo "🛑 Остановка всех ботов..."
        bots=$(find_all_bots)
        count=0
        
        while IFS='|' read -r tutor_id tutor_dir; do
            if systemctl is-active --quiet "tg-bot-${tutor_id}.service" 2>/dev/null; then
                echo "⏹️  Останавливаю бота $tutor_id..."
                sudo systemctl stop "tg-bot-${tutor_id}.service"
                ((count++))
            fi
        done <<< "$bots"
        
        echo "✅ Остановлено ботов: $count"
        ;;
    
    restart)
        echo "🔄 Перезапуск всех ботов..."
        $0 stop
        sleep 2
        $0 start
        ;;
    
    status)
        echo "📊 Статус всех ботов:"
        echo "=" | awk '{printf "%60s\n", $0}'
        bots=$(find_all_bots)
        
        if [ -z "$bots" ]; then
            echo "❌ Боты не найдены в папке tutors/"
            exit 1
        fi
        
        while IFS='|' read -r tutor_id tutor_dir; do
            if systemctl is-active --quiet "tg-bot-${tutor_id}.service" 2>/dev/null; then
                status="✅ Запущен"
            else
                status="❌ Остановлен"
            fi
            printf "👨‍🏫 ID: %-10s | %s\n" "$tutor_id" "$status"
        done <<< "$bots"
        ;;
    
    *)
        echo "Использование: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac

