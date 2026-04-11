#!/usr/bin/env python3
"""
Скрипт для запуска всех ботов репетиторов одновременно
Запускает run.py из каждой папки tutors/tutor_*/
"""

import os
import sys
import subprocess
import signal
import time
from pathlib import Path

# Цвета для вывода в терминал
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_colored(message, color=Colors.RESET):
    """Печать цветного сообщения"""
    print(f"{color}{message}{Colors.RESET}")

def find_all_tutor_bots(root_dir):
    """Находит все папки с ботами репетиторов"""
    tutors_dir = root_dir / "tutors"
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
                    'path': item,
                    'run_file': run_file
                })
    
    return sorted(tutor_folders, key=lambda x: x['id'])

def start_bot(tutor_info, root_dir):
    """Запускает один бот в отдельном процессе"""
    tutor_id = tutor_info['id']
    tutor_path = tutor_info['path']
    run_file = tutor_info['run_file']
    
    # Преобразуем пути в абсолютные
    tutor_path_abs = tutor_path.resolve()
    run_file_abs = run_file.resolve()
    
    # Определяем путь к виртуальному окружению
    venv_python = root_dir.resolve() / "venv" / "bin" / "python3"
    if not venv_python.exists():
        # Пробуем системный python3
        venv_python = Path("python3")
    
    try:
        # Запускаем бот с указанием рабочей директории
        process = subprocess.Popen(
            [str(venv_python), str(run_file_abs)],
            cwd=str(tutor_path_abs),  # Указываем рабочую директорию
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        return process, tutor_id
    except Exception as e:
        print_colored(f"❌ Ошибка запуска бота {tutor_id}: {e}", Colors.RED)
        return None, tutor_id

def main():
    """Главная функция"""
    # Получаем корневую директорию проекта
    root_dir = Path(__file__).parent.absolute()
    # Сохраняем текущую директорию, чтобы не менять её
    original_cwd = os.getcwd()
    
    print_colored("\n" + "=" * 60, Colors.BOLD)
    print_colored("🤖 Запуск всех ботов репетиторов", Colors.BOLD)
    print_colored("=" * 60, Colors.RESET)
    
    # Находим все боты (передаем root_dir для корректных путей)
    tutor_bots = find_all_tutor_bots(root_dir)
    
    if not tutor_bots:
        print_colored("\n❌ Не найдено ни одного бота в папке tutors/", Colors.RED)
        print_colored("💡 Используйте deploy_bot.py для создания ботов", Colors.YELLOW)
        sys.exit(1)
    
    print_colored(f"\n📋 Найдено ботов: {len(tutor_bots)}", Colors.BLUE)
    for bot in tutor_bots:
        print_colored(f"   👨‍🏫 ID: {bot['id']}", Colors.GREEN)
    
    print_colored("\n🚀 Запускаю боты...\n", Colors.BLUE)
    
    # Словарь для хранения процессов
    processes = {}
    
    # Запускаем все боты
    for tutor_info in tutor_bots:
        tutor_id = tutor_info['id']
        print_colored(f"▶️  Запускаю бота {tutor_id}...", Colors.YELLOW)
        
        process, pid = start_bot(tutor_info, root_dir)
        if process:
            processes[tutor_id] = process
            time.sleep(1)  # Небольшая задержка между запусками
            print_colored(f"✅ Бот {tutor_id} запущен (PID: {process.pid})", Colors.GREEN)
        else:
            print_colored(f"❌ Не удалось запустить бота {tutor_id}", Colors.RED)
    
    if not processes:
        print_colored("\n❌ Не удалось запустить ни одного бота", Colors.RED)
        sys.exit(1)
    
    print_colored(f"\n✅ Успешно запущено ботов: {len(processes)}/{len(tutor_bots)}", Colors.GREEN)
    print_colored("\n📊 Мониторинг процессов (Ctrl+C для остановки):\n", Colors.BLUE)
    
    # Функция для корректного завершения
    def signal_handler(sig, frame):
        print_colored("\n\n⏹️  Получен сигнал остановки. Завершаю все процессы...", Colors.YELLOW)
        for tutor_id, process in processes.items():
            try:
                print_colored(f"🛑 Останавливаю бота {tutor_id}...", Colors.YELLOW)
                process.terminate()
                process.wait(timeout=5)
                print_colored(f"✅ Бот {tutor_id} остановлен", Colors.GREEN)
            except subprocess.TimeoutExpired:
                print_colored(f"⚠️  Принудительное завершение бота {tutor_id}...", Colors.RED)
                process.kill()
                process.wait()
            except Exception as e:
                print_colored(f"❌ Ошибка при остановке бота {tutor_id}: {e}", Colors.RED)
        
        print_colored("\n👋 Все боты остановлены. До свидания!", Colors.BLUE)
        sys.exit(0)
    
    # Регистрируем обработчик сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Мониторинг процессов
    try:
        while True:
            time.sleep(5)
            
            # Проверяем статус всех процессов
            for tutor_id, process in list(processes.items()):
                if process.poll() is not None:
                    # Процесс завершился
                    return_code = process.returncode
                    stdout, stderr = process.communicate()
                    
                    if return_code == 0:
                        print_colored(f"⚠️  Бот {tutor_id} завершился нормально (код: {return_code})", Colors.YELLOW)
                    else:
                        print_colored(f"❌ Бот {tutor_id} завершился с ошибкой (код: {return_code})", Colors.RED)
                        if stderr:
                            print_colored(f"   Ошибка: {stderr[:200]}", Colors.RED)
                    
                    # Удаляем из списка
                    del processes[tutor_id]
            
            # Если все процессы завершились
            if not processes:
                print_colored("\n⚠️  Все боты завершили работу", Colors.YELLOW)
                break
            
            # Выводим статус
            active_count = len(processes)
            print(f"{Colors.GREEN}💚 Активных ботов: {active_count}{Colors.RESET}", end="\r")
    
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == "__main__":
    main()

