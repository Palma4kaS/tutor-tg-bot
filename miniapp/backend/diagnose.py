#!/usr/bin/env python3
"""
Диагностический скрипт для проверки конфигурации miniapp backend
"""
import os
import sys
import sqlite3
from pathlib import Path

def check_env_file():
    """Проверка .env файла"""
    print("=" * 60)
    print("1. Проверка .env файла")
    print("=" * 60)

    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        print("❌ Файл .env НЕ НАЙДЕН!")
        return False

    print(f"✅ Файл .env найден: {env_path}")

    with open(env_path) as f:
        content = f.read()
        print("\nСодержимое .env:")
        for line in content.split('\n'):
            if line.strip() and not line.startswith('#'):
                key = line.split('=')[0]
                if 'TOKEN' in key:
                    print(f"  {key}=***скрыто***")
                else:
                    print(f"  {line}")
    return True

def check_config():
    """Проверка config.py"""
    print("\n" + "=" * 60)
    print("2. Проверка конфигурации")
    print("=" * 60)

    try:
        from config import DB_PATH, BOT_TOKEN, TUTOR_FOLDER

        print(f"TUTOR_FOLDER: {TUTOR_FOLDER}")
        print(f"DB_PATH: {DB_PATH}")
        print(f"BOT_TOKEN: {'✅ установлен' if BOT_TOKEN else '❌ НЕ установлен'}")

        return DB_PATH, BOT_TOKEN
    except Exception as e:
        print(f"❌ Ошибка при импорте config: {e}")
        return None, None

def check_db_file(db_path):
    """Проверка файла базы данных"""
    print("\n" + "=" * 60)
    print("3. Проверка файла базы данных")
    print("=" * 60)

    if not db_path:
        print("❌ DB_PATH не определен")
        return False

    print(f"Ожидаемый путь к БД: {db_path}")

    db_file = Path(db_path)

    if not db_file.exists():
        print(f"❌ Файл БД НЕ НАЙДЕН: {db_path}")
        print("\nВозможные причины:")
        print("1. БД не скопирована на сервер")
        print("2. Неправильный путь в TUTOR_FOLDER")

        # Попробуем найти БД
        print("\nПоиск файлов tutor_bot.db:")
        base_dir = Path(__file__).parent.parent.parent
        for db_file in base_dir.rglob("tutor_bot.db"):
            print(f"  Найдена БД: {db_file}")
            print(f"    Размер: {db_file.stat().st_size} байт")

        return False

    print(f"✅ Файл БД найден: {db_path}")
    print(f"   Размер: {db_file.stat().st_size} байт")

    # Проверяем права доступа
    if not os.access(db_path, os.R_OK):
        print(f"❌ НЕТ прав на чтение БД!")
        print(f"   Текущий пользователь: {os.getenv('USER')}")
        return False

    print(f"✅ Права на чтение: есть")

    # Проверяем структуру БД
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Получаем список таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        print(f"\nТаблицы в БД: {', '.join(tables)}")

        # Проверяем таблицу students
        if 'students' in tables:
            cursor.execute("SELECT COUNT(*) FROM students")
            count = cursor.fetchone()[0]
            print(f"✅ Таблица students: {count} записей")

            # Проверяем наличие конкретного ученика
            cursor.execute("SELECT user_id, name FROM students LIMIT 5")
            students = cursor.fetchall()
            print("\nПримеры учеников в БД:")
            for user_id, name in students:
                print(f"  - user_id={user_id}, name={name}")
        else:
            print("❌ Таблица students НЕ НАЙДЕНА")
            conn.close()
            return False

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Ошибка при проверке БД: {e}")
        return False

def check_api_endpoint():
    """Проверка работы API"""
    print("\n" + "=" * 60)
    print("4. Проверка API endpoint")
    print("=" * 60)

    try:
        import subprocess
        result = subprocess.run(
            ["curl", "-s", "http://127.0.0.1:8000/health"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout:
            print(f"✅ Backend отвечает: {result.stdout}")
            return True
        else:
            print(f"❌ Backend НЕ отвечает")
            print("Попробуйте запустить: systemctl status miniapp-api")
            return False
    except Exception as e:
        print(f"⚠️  Не удалось проверить API: {e}")
        return False

def check_frontend_build():
    """Проверка сборки frontend"""
    print("\n" + "=" * 60)
    print("5. Проверка frontend")
    print("=" * 60)

    frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"

    if not frontend_dist.exists():
        print(f"❌ Frontend НЕ собран: {frontend_dist}")
        print("Запустите: cd frontend && npm run build")
        return False

    print(f"✅ Frontend собран: {frontend_dist}")

    index_file = frontend_dist / "index.html"
    if index_file.exists():
        print(f"✅ index.html найден")
    else:
        print(f"❌ index.html НЕ найден")
        return False

    # Проверяем .env для production
    frontend_env = Path(__file__).parent.parent / "frontend" / ".env"
    if frontend_env.exists():
        print(f"✅ Frontend .env найден")
        with open(frontend_env) as f:
            print("   Содержимое:")
            for line in f:
                print(f"     {line.rstrip()}")
    else:
        print(f"⚠️  Frontend .env не найден (может использоваться /api по умолчанию)")

    return True

def main():
    print("\n🔍 ДИАГНОСТИКА MINIAPP BACKEND\n")

    results = []

    results.append(("Файл .env", check_env_file()))

    db_path, bot_token = check_config()
    results.append(("Конфигурация", db_path is not None and bot_token is not None))

    results.append(("База данных", check_db_file(db_path)))
    results.append(("API endpoint", check_api_endpoint()))
    results.append(("Frontend", check_frontend_build()))

    # Итоги
    print("\n" + "=" * 60)
    print("ИТОГИ ДИАГНОСТИКИ")
    print("=" * 60)

    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}")

    all_ok = all(result for _, result in results)

    if all_ok:
        print("\n✅ Все проверки пройдены успешно!")
    else:
        print("\n❌ Обнаружены проблемы. См. детали выше.")
        print("\nРекомендации:")
        print("1. Проверьте логи: journalctl -u miniapp-api -n 50")
        print("2. Проверьте nginx: systemctl status nginx")
        print("3. Проверьте файлы на сервере")

    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
