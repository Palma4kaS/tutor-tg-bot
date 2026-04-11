#!/usr/bin/env python3
"""
Скрипт для обновления run.py во всех папках учителей
Обновляет только run.py, не трогает .env, config.py и базу данных
"""

import os
import shutil
from pathlib import Path

def update_all_run_files():
    """Обновить run.py во всех папках учителей"""
    
    # Проверяем наличие bot_template/run.py
    template_run = "bot_template/run.py"
    if not os.path.exists(template_run):
        print(f"❌ Ошибка: файл {template_run} не найден!")
        return False
    
    # Проверяем наличие папки tutors
    if not os.path.exists("tutors"):
        print("❌ Папка tutors не найдена!")
        return False
    
    # Находим все папки учителей
    tutors_dir = Path("tutors")
    tutor_folders = [d for d in tutors_dir.iterdir() if d.is_dir() and d.name.startswith("tutor_")]
    
    if not tutor_folders:
        print("📂 Папки учителей не найдены")
        return False
    
    print("=" * 60)
    print("🔄 Обновление run.py во всех папках учителей")
    print("=" * 60)
    print(f"\n📋 Найдено папок: {len(tutor_folders)}")
    
    updated_count = 0
    skipped_count = 0
    error_count = 0
    
    for tutor_folder in sorted(tutor_folders):
        tutor_id = tutor_folder.name.replace("tutor_", "")
        run_path = tutor_folder / "run.py"
        
        try:
            # Проверяем, существует ли папка и run.py
            if not tutor_folder.exists():
                print(f"⚠️  Пропущено: {tutor_folder.name} (папка не существует)")
                skipped_count += 1
                continue
            
            # Копируем run.py
            shutil.copy2(template_run, run_path)
            updated_count += 1
            print(f"✅ Обновлено: {tutor_folder.name} (ID: {tutor_id})")
            
        except Exception as e:
            error_count += 1
            print(f"❌ Ошибка при обновлении {tutor_folder.name}: {e}")
    
    print("\n" + "=" * 60)
    print("📊 Результаты:")
    print(f"   ✅ Обновлено: {updated_count}")
    if skipped_count > 0:
        print(f"   ⚠️  Пропущено: {skipped_count}")
    if error_count > 0:
        print(f"   ❌ Ошибок: {error_count}")
    print("=" * 60)
    
    return error_count == 0

def update_single_run_file(tutor_id: str):
    """Обновить run.py для конкретного учителя"""
    
    # Проверяем наличие bot_template/run.py
    template_run = "bot_template/run.py"
    if not os.path.exists(template_run):
        print(f"❌ Ошибка: файл {template_run} не найден!")
        return False
    
    tutor_folder = f"tutors/tutor_{tutor_id}"
    run_path = os.path.join(tutor_folder, "run.py")
    
    if not os.path.exists(tutor_folder):
        print(f"❌ Папка {tutor_folder} не найдена!")
        return False
    
    try:
        shutil.copy2(template_run, run_path)
        print(f"✅ run.py обновлен для учителя {tutor_id}")
        return True
    except Exception as e:
        print(f"❌ Ошибка при обновлении: {e}")
        return False

def list_tutors():
    """Показать список всех учителей"""
    if not os.path.exists("tutors"):
        print("📂 Папка tutors не найдена")
        return
    
    tutors_dir = Path("tutors")
    tutor_folders = [d for d in tutors_dir.iterdir() if d.is_dir() and d.name.startswith("tutor_")]
    
    if not tutor_folders:
        print("📂 Папки учителей не найдены")
        return
    
    print("\n📋 Список учителей:")
    print("=" * 60)
    for tutor_folder in sorted(tutor_folders):
        tutor_id = tutor_folder.name.replace("tutor_", "")
        run_path = tutor_folder / "run.py"
        run_exists = "✅" if run_path.exists() else "❌"
        print(f"👨‍🏫 ID: {tutor_id} | run.py {run_exists}")
    print("=" * 60)

if __name__ == "__main__":
    print("\n🔄 Обновление run.py для учителей")
    print("\n" + "=" * 60)
    print("1. Обновить run.py для всех учителей")
    print("2. Обновить run.py для конкретного учителя")
    print("3. Показать список учителей")
    print("4. Выход")
    print("=" * 60)
    
    choice = input("\nВыберите действие (1-4): ").strip()
    
    if choice == "1":
        print("\n⚠️  Внимание: будут обновлены run.py во всех папках учителей")
        confirm = input("Продолжить? (yes/no): ").strip().lower()
        if confirm == "yes":
            success = update_all_run_files()
            if success:
                print("\n🎉 Обновление завершено успешно!")
            else:
                print("\n⚠️  Обновление завершено с ошибками")
        else:
            print("❌ Отменено")
    
    elif choice == "2":
        tutor_id = input("\n📝 Введите ID учителя: ").strip()
        if tutor_id:
            update_single_run_file(tutor_id)
        else:
            print("❌ ID не может быть пустым!")
    
    elif choice == "3":
        list_tutors()
    
    else:
        print("👋 До свидания!")

