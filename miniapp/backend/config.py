import os
from dotenv import load_dotenv
from datetime import timezone, timedelta
from pathlib import Path

# Загружаем переменные окружения
load_dotenv()

# Московское время (UTC+3)
MOSCOW_TZ = timezone(timedelta(hours=3))

# Базовая директория проекта
BASE_DIR = Path(__file__).parent.parent.parent

# MULTI-TENANT CONFIGURATION
# Маппинг bot_token -> tutor_folder для поддержки нескольких ботов.
# Задаётся в bots_config.py (не отслеживается git).
# Скопируй bots_config.py.example -> bots_config.py и заполни своими токенами.
try:
    from bots_config import BOTS_CONFIG
except ImportError:
    BOTS_CONFIG = {}


def _load_bots_admins() -> dict[str, list[int]]:
    """Читает TUTOR_ID и ADMIN_ID из .env каждого тутора автоматически"""
    admins: dict[str, list[int]] = {}
    for tutor_folder in BOTS_CONFIG.values():
        env_path = BASE_DIR / 'tutors' / tutor_folder / '.env'
        if not env_path.exists():
            continue
        ids: list[int] = []
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                for key in ('TUTOR_ID', 'ADMIN_ID'):
                    if line.startswith(f'{key}='):
                        try:
                            val = int(line.split('=', 1)[1])
                            if val != 0 and val not in ids:
                                ids.append(val)
                        except ValueError:
                            pass
        admins[tutor_folder] = ids
    return admins


# Маппинг tutor_folder -> [TUTOR_ID, ADMIN_ID], подгружается из .env каждого тутора
BOTS_ADMINS = _load_bots_admins()


def get_admins_for_tutor(tutor_folder: str) -> list[int]:
    """Получить список ID администраторов для конкретного репетитора"""
    return BOTS_ADMINS.get(tutor_folder, [])


def get_db_path_for_tutor(tutor_folder: str) -> str:
    """Получить путь к БД для конкретного репетитора"""
    return str(BASE_DIR / 'tutors' / tutor_folder / 'tutor_bot.db')

# Старые переменные для обратной совместимости (используются при отсутствии multi-tenant)
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
TUTOR_FOLDER = os.getenv('TUTOR_FOLDER', '')
if TUTOR_FOLDER:
    DB_PATH = get_db_path_for_tutor(TUTOR_FOLDER)
else:
    DB_PATH = os.getenv('DB_PATH', 'tutor_bot.db')

# CORS настройки
CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')

# API настройки
API_PREFIX = ''
