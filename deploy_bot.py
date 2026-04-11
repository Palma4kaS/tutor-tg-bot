import os
import shutil

def create_new_tutor_bot():
    print("=" * 50)
    print("🤖 Создание нового бота для репетитора")
    print("=" * 50)
    tutor_id = input("\n📝 Введите Telegram ID репетитора: ").strip()
    bot_token = input("🔑 Введите токен бота от BotFather: ").strip()
    admin_id = input("👑 Введите Admin ID (Enter = ID репетитора): ").strip() or tutor_id

    if not tutor_id.isdigit():
        print("❌ Ошибка: ID должен быть числом!")
        return
    if not bot_token:
        print("❌ Ошибка: токен не может быть пустым!")
        return

    tutor_folder = f"tutors/tutor_{tutor_id}"

    # Обработка существующей папки
    if os.path.exists(tutor_folder):
        print(f"⚠️ Папка {tutor_folder} уже существует!")
        overwrite = input("Перезаписать код бота? База данных сохранится (yes/no): ").strip().lower()
        if overwrite != 'yes':
            print("❌ Отменено")
            return
        
        # Сохраняем важные файлы
        env_path = os.path.join(tutor_folder, ".env")
        db_path = os.path.join(tutor_folder, "tutor_bot.db")
        
        env_backup = None
        db_backup = None
        
        # Бэкапим .env
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as env_file:
                env_backup = env_file.read()
        
        # Бэкапим базу данных (бинарный режим!)
        if os.path.exists(db_path):
            with open(db_path, "rb") as db_file:
                db_backup = db_file.read()
        
        # Удаляем папку и пересоздаем
        shutil.rmtree(tutor_folder)
        os.makedirs(tutor_folder, exist_ok=True)
        
        # Восстанавливаем файлы
        if env_backup is not None:
            with open(env_path, "w", encoding="utf-8") as env_file:
                env_file.write(env_backup)
            print("✅ Восстановлен .env")
        
        if db_backup is not None:
            with open(db_path, "wb") as db_file:
                db_file.write(db_backup)
            print("✅ Восстановлена база данных")

    else:
        os.makedirs(tutor_folder, exist_ok=True)

    # Копируем только необходимые файлы
    shutil.copy("bot_template/config.py", f"{tutor_folder}/config.py")
    shutil.copy("bot_template/run.py", f"{tutor_folder}/run.py")

    # Создаем .env с правильными переменными
    with open(f"{tutor_folder}/.env", "w", encoding="utf-8") as f:
        f.write(f"BOT_TOKEN={bot_token}\n")
        f.write(f"TUTOR_ID={tutor_id}\n")
        f.write(f"ADMIN_ID={admin_id}\n")
        f.write(f"DATABASE_URL=sqlite:///bot_data.db\n")

    print("✅ Обновлены файлы: config.py, run.py, .env")

    print("\n" + "=" * 50)
    print("✅ Бот успешно создан/обновлен!")
    print("=" * 50)
    print(f"\n📂 Папка бота: {tutor_folder}")
    print(f"\n📝 Следующие шаги:")
    print(f"1. Перейдите в папку: cd {tutor_folder}")
    print(f"2. (Опционально) Настройте цены в config.py")
    print(f"3. Запустите бота: python run.py")
    print(f"\n💡 Общий код (handlers, keyboards, db_manager) используется из bot_template/")
    print(f"💾 База данных и настройки сохранены при обновлении")
    print("\n🎉 Готово!")

def list_all_bots():
    if not os.path.exists("tutors"):
        print("📂 Папка tutors не найдена")
        return

    tutors = [d for d in os.listdir("tutors") if d.startswith("tutor_")]
    if not tutors:
        print("📂 Боты не найдены")
        return

    print("\n📋 Список ботов:")
    print("=" * 50)
    for tutor in tutors:
        tutor_id = tutor.replace("tutor_", "")
        db_path = f"tutors/{tutor}/tutor_bot.db"
        env_path = f"tutors/{tutor}/.env"
        run_path = f"tutors/{tutor}/run.py"
        
        db_exists = "✅" if os.path.exists(db_path) else "❌"
        env_exists = "✅" if os.path.exists(env_path) else "❌"
        run_exists = "✅" if os.path.exists(run_path) else "❌"
        
        print(f"👨‍🏫 ID: {tutor_id} | БД {db_exists} | .env {env_exists} | run.py {run_exists}")
    print("=" * 50)

if __name__ == "__main__":
    print("\n🤖 Управление ботами репетиторов")
    print("\n📋 Архитектура:")
    print("   • Общий код: bot_template/ (handlers, keyboards, db_manager)")
    print("   • Индивидуально: tutors/tutor_<ID>/ (config, .env, БД)")
    print("\n" + "=" * 50)
    print("1. Создать/перезаписать бота")
    print("2. Показать список ботов")
    print("3. Выход")
    choice = input("\nВыберите действие (1-3): ").strip()
    
    if choice == "1":
        create_new_tutor_bot()
    elif choice == "2":
        list_all_bots()
    else:
        print("👋 До свидания!")
