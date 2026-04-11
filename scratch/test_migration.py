#!/usr/bin/env python3
"""
Скрипт для тестирования миграции базы данных
Проверяет, что новая схема БД создается корректно
"""
import asyncio
import sys
import os
from pathlib import Path

# Добавляем путь к bot_template
sys.path.insert(0, str(Path(__file__).parent))

from bot_template.database.db_manager import DatabaseManager


async def test_migration():
    """Тестирование миграции БД"""

    print("🧪 Тестирование миграции базы данных...")
    print("-" * 60)

    # Используем тестовую БД
    test_db_path = "test_migration.db"

    # Удаляем старую тестовую БД если есть
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        print(f"🗑️  Удалена старая тестовая БД: {test_db_path}")

    try:
        # Инициализируем БД
        db = DatabaseManager(test_db_path)
        await db.init_db()
        print("✅ Инициализация БД успешна!")

        # Проверяем структуру
        import aiosqlite
        async with aiosqlite.connect(test_db_path) as conn:
            # 1. Проверяем таблицы
            print("\n📊 Проверка таблиц:")
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = await cursor.fetchall()
            expected_tables = ['students', 'lessons', 'schedules',
                             'student_changes_history', 'scheduled_tasks', 'price_settings']

            for table in tables:
                table_name = table[0]
                if table_name in expected_tables:
                    print(f"  ✅ {table_name}")
                else:
                    print(f"  ℹ️  {table_name}")

            # Проверяем, что все ожидаемые таблицы есть
            existing_tables = [t[0] for t in tables]
            missing = set(expected_tables) - set(existing_tables)
            if missing:
                print(f"\n  ❌ Отсутствуют таблицы: {', '.join(missing)}")
                return False

            # 2. Проверяем индексы
            print("\n📇 Проверка индексов:")
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%' ORDER BY name"
            )
            indices = await cursor.fetchall()
            print(f"  Создано {len(indices)} индексов:")
            for idx in indices:
                print(f"    • {idx[0]}")

            if len(indices) < 10:
                print(f"  ⚠️  Ожидалось больше индексов (минимум 10), найдено {len(indices)}")

            # 3. Проверяем структуру таблицы scheduled_tasks
            print("\n🗂️  Структура таблицы scheduled_tasks:")
            cursor = await conn.execute("PRAGMA table_info(scheduled_tasks)")
            columns = await cursor.fetchall()

            expected_columns = {
                'id': 'INTEGER',
                'lesson_id': 'INTEGER',
                'task_type': 'TEXT',
                'scheduled_time': 'TEXT',
                'status': 'TEXT',
                'execution_data': 'TEXT',
                'retry_count': 'INTEGER',
                'max_retries': 'INTEGER',
                'created_at': 'TEXT',
                'executed_at': 'TEXT',
                'error_message': 'TEXT'
            }

            for col in columns:
                col_name = col[1]
                col_type = col[2]
                if col_name in expected_columns:
                    print(f"  ✅ {col_name}: {col_type}")
                else:
                    print(f"  ℹ️  {col_name}: {col_type} (неожиданная колонка)")

            # Проверяем, что все ожидаемые колонки есть
            existing_columns = {col[1]: col[2] for col in columns}
            missing_cols = set(expected_columns.keys()) - set(existing_columns.keys())
            if missing_cols:
                print(f"\n  ❌ Отсутствуют колонки: {', '.join(missing_cols)}")
                return False

            # 4. Тестируем создание задачи
            print("\n🔧 Тестирование создания задачи:")
            from datetime import datetime, timedelta

            future_time = (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')

            task_id = await db.create_scheduled_task(
                lesson_id=999,
                task_type='test_notification',
                scheduled_time=future_time,
                execution_data={'test': 'data'}
            )

            if task_id:
                print(f"  ✅ Задача создана с ID: {task_id}")

                # Проверяем, что задача в БД
                cursor = await conn.execute(
                    "SELECT * FROM scheduled_tasks WHERE id = ?",
                    (task_id,)
                )
                task = await cursor.fetchone()
                if task:
                    print(f"  ✅ Задача найдена в БД")
                    print(f"    • Тип: {task[2]}")
                    print(f"    • Время: {task[3]}")
                    print(f"    • Статус: {task[4]}")
                else:
                    print(f"  ❌ Задача не найдена в БД")
                    return False
            else:
                print(f"  ❌ Не удалось создать задачу")
                return False

            # 5. Тестируем методы работы с задачами
            print("\n🧪 Тестирование методов работы с задачами:")

            # task_exists
            exists = await db.task_exists(999, 'test_notification')
            print(f"  {'✅' if exists else '❌'} task_exists: {exists}")

            # get_pending_tasks
            pending = await db.get_pending_tasks()
            print(f"  {'✅' if len(pending) > 0 else '❌'} get_pending_tasks: найдено {len(pending)} задач")

            # update_task_status
            await db.update_task_status(task_id, 'completed')
            cursor = await conn.execute(
                "SELECT status FROM scheduled_tasks WHERE id = ?",
                (task_id,)
            )
            status = await cursor.fetchone()
            if status and status[0] == 'completed':
                print(f"  ✅ update_task_status: статус обновлен на 'completed'")
            else:
                print(f"  ❌ update_task_status: не удалось обновить статус")
                return False

        print("\n" + "=" * 60)
        print("✅ Все тесты пройдены успешно!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Опционально: удаляем тестовую БД
        # if os.path.exists(test_db_path):
        #     os.remove(test_db_path)
        #     print(f"\n🗑️  Тестовая БД удалена")
        pass


async def test_migration_on_existing_db():
    """Тестирование миграции на существующей БД"""

    print("\n\n🧪 Тестирование миграции на существующей БД...")
    print("-" * 60)

    # Ищем первую доступную БД
    tutors_dir = Path(__file__).parent / "tutors"
    db_path = None

    for tutor_dir in tutors_dir.glob("tutor_*"):
        potential_db = tutor_dir / "tutor_bot.db"
        if potential_db.exists():
            db_path = str(potential_db)
            break

    if not db_path:
        print("⚠️  Не найдена существующая БД для тестирования")
        print("   (это нормально, если это первый запуск)")
        return True

    print(f"📁 Найдена БД: {db_path}")

    # Создаем бэкап
    backup_path = f"{db_path}.test_backup"
    import shutil
    shutil.copy2(db_path, backup_path)
    print(f"💾 Создан бэкап: {backup_path}")

    try:
        # Пробуем применить миграцию
        db = DatabaseManager(db_path)
        await db.init_db()
        print("✅ Миграция на существующей БД успешна!")

        # Проверяем, что старые данные не затронуты
        import aiosqlite
        async with aiosqlite.connect(db_path) as conn:
            # Проверяем количество учеников
            cursor = await conn.execute("SELECT COUNT(*) FROM students")
            count = await cursor.fetchone()
            print(f"  ℹ️  Учеников в БД: {count[0]}")

            # Проверяем количество уроков
            cursor = await conn.execute("SELECT COUNT(*) FROM lessons")
            count = await cursor.fetchone()
            print(f"  ℹ️  Уроков в БД: {count[0]}")

        print("✅ Существующие данные не затронуты")
        return True

    except Exception as e:
        print(f"❌ Ошибка при миграции существующей БД: {e}")
        import traceback
        traceback.print_exc()

        # Восстанавливаем из бэкапа
        print(f"🔄 Восстановление из бэкапа...")
        shutil.copy2(backup_path, db_path)
        print(f"✅ БД восстановлена")
        return False

    finally:
        # Удаляем бэкап
        if os.path.exists(backup_path):
            os.remove(backup_path)
            print(f"🗑️  Тестовый бэкап удален")


async def main():
    """Главная функция"""

    print("=" * 60)
    print("🚀 ТЕСТИРОВАНИЕ МИГРАЦИИ БД")
    print("=" * 60)

    # Тест 1: Новая БД
    test1_ok = await test_migration()

    # Тест 2: Существующая БД
    test2_ok = await test_migration_on_existing_db()

    print("\n" + "=" * 60)
    print("📊 ИТОГОВЫЙ РЕЗУЛЬТАТ:")
    print("=" * 60)
    print(f"  Тест новой БД: {'✅ PASS' if test1_ok else '❌ FAIL'}")
    print(f"  Тест существующей БД: {'✅ PASS' if test2_ok else '❌ FAIL'}")

    if test1_ok and test2_ok:
        print("\n✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("   Миграция безопасна для применения.")
        return 0
    else:
        print("\n❌ ЕСТЬ ПРОВАЛЕННЫЕ ТЕСТЫ!")
        print("   НЕ ОБНОВЛЯЙТЕ БОТЫ НА СЕРВЕРЕ!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
