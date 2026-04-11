#!/usr/bin/env python3
"""
Скрипт для добавления нового бота в multi-tenant систему miniapp.

Usage:
    python add_bot.py
"""
import sys
import re
from pathlib import Path


def validate_bot_token(token: str) -> bool:
    """Проверить формат токена бота"""
    # Формат: 123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    pattern = r'^\d+:[A-Za-z0-9_-]{35}$'
    return bool(re.match(pattern, token))


def get_bot_info(token: str) -> dict:
    """Получить информацию о боте через API"""
    try:
        import requests  # type: ignore
        response = requests.get(f'https://api.telegram.org/bot{token}/getMe', timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                bot_data = data['result']
                return {
                    'id': bot_data['id'],
                    'username': bot_data.get('username', 'unknown'),
                    'first_name': bot_data.get('first_name', 'Bot')
                }
    except Exception as e:
        print(f"⚠️  Не удалось получить информацию о боте: {e}")
    return None


def check_tutor_folder(tutor_folder: str) -> dict:
    """Проверить наличие папки репетитора и БД"""
    base_dir = Path(__file__).parent.parent.parent
    tutor_path = base_dir / 'tutors' / tutor_folder
    db_path = tutor_path / 'tutor_bot.db'

    return {
        'folder_exists': tutor_path.exists(),
        'db_exists': db_path.exists(),
        'tutor_path': tutor_path,
        'db_path': db_path
    }


def add_bot_to_config(bot_token: str, tutor_folder: str, comment: str = "") -> bool:
    """Добавить бота в BOTS_CONFIG в config.py"""
    config_path = Path(__file__).parent / 'config.py'

    # Читаем config.py
    with open(config_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Ищем BOTS_CONFIG
    config_start = -1
    config_end = -1

    for i, line in enumerate(lines):
        if 'BOTS_CONFIG = {' in line:
            config_start = i
        if config_start != -1 and line.strip() == '}':
            config_end = i
            break

    if config_start == -1:
        print("❌ Не найден BOTS_CONFIG в config.py")
        return False

    # Проверяем, есть ли уже такой токен
    for line in lines[config_start:config_end]:
        if bot_token in line:
            print("⚠️  Этот токен уже есть в конфигурации")
            return False

    # Добавляем новую запись перед закрывающей скобкой
    comment_str = f"  # {comment}" if comment else ""
    new_entry = f"    '{bot_token}': '{tutor_folder}',{comment_str}\n"
    lines.insert(config_end, new_entry)

    # Записываем обратно
    with open(config_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    return True


def main():
    print("=" * 70)
    print("🤖 ДОБАВЛЕНИЕ НОВОГО БОТА В MINIAPP")
    print("=" * 70)
    print()

    # Шаг 1: Получаем токен бота
    print("Шаг 1: Введите токен бота")
    print("Формат: 123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    bot_token = input("Bot Token: ").strip()

    if not validate_bot_token(bot_token):
        print("❌ Неверный формат токена бота")
        return 1

    print("✅ Формат токена корректен")

    # Пробуем получить информацию о боте
    print("\nПолучаем информацию о боте...")
    bot_info = get_bot_info(bot_token)

    if bot_info:
        print(f"✅ Бот найден:")
        print(f"   ID: {bot_info['id']}")
        print(f"   Username: @{bot_info['username']}")
        print(f"   Name: {bot_info['first_name']}")

        suggested_folder = f"tutor_{bot_info['id']}"
    else:
        print("⚠️  Не удалось получить информацию о боте")
        print("   Возможно, токен неверный или нет доступа к интернету")

        # Спрашиваем ID вручную
        print("\nВведите TUTOR_ID (Telegram user_id учителя):")
        tutor_id = input("TUTOR_ID: ").strip()

        if not tutor_id.isdigit():
            print("❌ ID должен быть числом")
            return 1

        suggested_folder = f"tutor_{tutor_id}"

    # Шаг 2: Определяем папку репетитора
    print(f"\nШаг 2: Папка репетитора")
    print(f"Рекомендуемое название: {suggested_folder}")
    folder_input = input(f"Введите название папки [{suggested_folder}]: ").strip()
    tutor_folder = folder_input if folder_input else suggested_folder

    # Проверяем папку
    folder_info = check_tutor_folder(tutor_folder)

    if folder_info['folder_exists']:
        print(f"✅ Папка найдена: {folder_info['tutor_path']}")

        if folder_info['db_exists']:
            print(f"✅ База данных найдена: {folder_info['db_path']}")
            db_size = folder_info['db_path'].stat().st_size
            print(f"   Размер БД: {db_size} байт")
        else:
            print(f"❌ База данных НЕ найдена: {folder_info['db_path']}")
            print("   Убедитесь, что БД бота скопирована в эту папку")

            proceed = input("\nПродолжить без БД? (yes/no): ").strip().lower()
            if proceed not in ['yes', 'y', 'да', 'д']:
                print("Отменено")
                return 1
    else:
        print(f"❌ Папка НЕ найдена: {folder_info['tutor_path']}")
        print("\nНеобходимо:")
        print(f"1. Создать папку: tutors/{tutor_folder}")
        print(f"2. Скопировать tutor_bot.db в tutors/{tutor_folder}/")
        print(f"3. Скопировать run.py и config.py бота (опционально)")

        proceed = input("\nПродолжить? Папка будет создана. (yes/no): ").strip().lower()
        if proceed not in ['yes', 'y', 'да', 'д']:
            print("Отменено")
            return 1

        # Создаем папку
        folder_info['tutor_path'].mkdir(parents=True, exist_ok=True)
        print(f"✅ Папка создана: {folder_info['tutor_path']}")

    # Шаг 3: Комментарий для конфига
    print(f"\nШаг 3: Описание (опционально)")
    comment = input("Описание бота (например, 'Бот Иванова'): ").strip()

    # Шаг 4: Подтверждение
    print("\n" + "=" * 70)
    print("ИТОГО:")
    print("=" * 70)
    print(f"Bot Token: {bot_token[:15]}...{bot_token[-10:]}")
    print(f"Папка: tutors/{tutor_folder}")
    if comment:
        print(f"Описание: {comment}")
    print()

    confirm = input("Добавить бота в конфигурацию? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y', 'да', 'д']:
        print("Отменено")
        return 1

    # Добавляем в config.py
    if add_bot_to_config(bot_token, tutor_folder, comment):
        print("\n✅ Бот успешно добавлен в config.py!")

        print("\n" + "=" * 70)
        print("ДАЛЬНЕЙШИЕ ДЕЙСТВИЯ:")
        print("=" * 70)
        print("1. Проверьте изменения в miniapp/backend/config.py")
        print("2. Закоммитьте изменения:")
        print("   git add miniapp/backend/config.py")
        print(f"   git commit -m 'Add bot for {tutor_folder}'")
        print("3. Отправьте на сервер:")
        print("   git push origin miniapp")
        print("4. На сервере:")
        print("   cd ~/TelegramBot/RebornTgBot")
        print("   git pull origin miniapp")
        print("   sudo systemctl restart miniapp-api")
        print("5. Проверьте логи:")
        print("   sudo journalctl -u miniapp-api -n 30 -f")
        print()

        if not folder_info['db_exists']:
            print("⚠️  ВАЖНО: Не забудьте скопировать БД!")
            print(f"   Путь: {folder_info['db_path']}")

        return 0
    else:
        print("\n❌ Ошибка при добавлении бота")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nОтменено пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
