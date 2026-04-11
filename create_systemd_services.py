#!/usr/bin/env python3
"""
Скрипт для автоматического создания systemd сервисов для всех ботов
"""

import os
import subprocess
from pathlib import Path

def find_all_tutor_bots():
    """Находит все папки с ботами репетиторов"""
    tutors_dir = Path("tutors")
    if not tutors_dir.exists():
        return []
    
    tutor_folders = []
    for item in tutors_dir.iterdir():
        if item.is_dir() and item.name.startswith("tutor_"):
            run_file = item / "run.py"
            env_file = item / ".env"
            if run_file.exists() and env_file.exists():
                tutor_id = item.name.replace("tutor_", "")
                tutor_folders.append({
                    'id': tutor_id,
                    'path': item.absolute()
                })
    
    return sorted(tutor_folders, key=lambda x: x['id'])

def create_systemd_service(tutor_info, root_dir, username):
    """Создает systemd сервис для одного бота"""
    tutor_id = tutor_info['id']
    tutor_path = tutor_info['path']
    
    venv_python = root_dir / "venv" / "bin" / "python3"
    run_file = tutor_path / "run.py"
    
    service_content = f"""[Unit]
Description=Telegram Bot Service for Tutor {tutor_id}
After=network.target

[Service]
Type=simple
User={username}
WorkingDirectory={tutor_path}
Environment="PATH={root_dir}/venv/bin"
ExecStart={venv_python} {run_file}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    service_name = f"tg-bot-{tutor_id}.service"
    service_path = Path(f"/etc/systemd/system/{service_name}")
    
    print(f"📝 Создаю сервис для бота {tutor_id}...")
    
    try:
        # Создаем временный файл
        temp_file = Path(f"/tmp/{service_name}")
        temp_file.write_text(service_content)
        
        # Копируем в systemd
        subprocess.run(
            ["sudo", "cp", str(temp_file), str(service_path)],
            check=True
        )
        
        # Удаляем временный файл
        temp_file.unlink()
        
        print(f"✅ Сервис создан: {service_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при создании сервиса для {tutor_id}: {e}")
        return False

def main():
    """Главная функция"""
    root_dir = Path(__file__).parent.absolute()
    
    print("=" * 60)
    print("🔧 Создание systemd сервисов для всех ботов")
    print("=" * 60)
    
    # Получаем имя пользователя
    username = os.getenv("SUDO_USER") or os.getenv("USER") or "root"
    print(f"\n👤 Пользователь: {username}")
    
    # Находим все боты
    tutor_bots = find_all_tutor_bots()
    
    if not tutor_bots:
        print("\n❌ Не найдено ни одного бота в папке tutors/")
        print("💡 Используйте deploy_bot.py для создания ботов")
        return
    
    print(f"\n📋 Найдено ботов: {len(tutor_bots)}")
    for bot in tutor_bots:
        print(f"   👨‍🏫 ID: {bot['id']}")
    
    # Подтверждение
    response = input("\n❓ Создать systemd сервисы для всех ботов? (yes/no): ").strip().lower()
    if response != 'yes':
        print("❌ Отменено")
        return
    
    # Создаем сервисы
    success_count = 0
    for tutor_info in tutor_bots:
        if create_systemd_service(tutor_info, root_dir, username):
            success_count += 1
    
    if success_count > 0:
        print(f"\n✅ Создано сервисов: {success_count}/{len(tutor_bots)}")
        print("\n📋 Следующие шаги:")
        print("1. Перезагрузите systemd: sudo systemctl daemon-reload")
        print("2. Включите автозапуск всех ботов:")
        for bot in tutor_bots:
            print(f"   sudo systemctl enable tg-bot-{bot['id']}.service")
        print("3. Запустите все боты:")
        for bot in tutor_bots:
            print(f"   sudo systemctl start tg-bot-{bot['id']}.service")
        print("\n💡 Или используйте: ./run_all_bots_systemd.sh start")
    else:
        print("\n❌ Не удалось создать ни одного сервиса")

if __name__ == "__main__":
    main()

