import os
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta

# Загружаем переменные окружения из .env файла

load_dotenv()

# Московское время (UTC+3)
MOSCOW_TZ = timezone(timedelta(hours=3))

def get_local_time() -> datetime:
    """
    Получить текущее московское время (UTC+3)
    Используется вместо datetime.now() для правильной работы с часовым поясом
    """
    return datetime.now(MOSCOW_TZ)

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
# Токен бота от BotFather
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# ID репетитора в Telegram (получает уведомления о новых учениках)
TUTOR_ID = int(os.getenv('TUTOR_ID', '0'))
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
ADMINS_IDS = [TUTOR_ID, ADMIN_ID]

# Определяем путь к базе данных
DB_PATH = os.path.join(CONFIG_DIR, 'tutor_bot.db')

# ===== НАСТРОЙКИ ЦЕН =====
# Вы можете изменить эти значения под свои тарифы

# Базовые цены по формату обучения
ONLINE = 1000    # Цена онлайн занятия (руб)
OFFLINE = 1500   # Цена оффлайн занятия (руб)

# Доплаты за сложность
PROFIL = 500     # Доплата за профильный уровень (руб)
CLASS_9 = 300    # Доплата за 9 класс (руб)
CLASS_10_11 = 500  # Доплата за 10-11 классы (руб)

# ===== НАСТРОЙКИ УВЕДОМЛЕНИЙ =====
LESSON_END_NOTIFICATION_MINUTES = 5      # За сколько минут до конца урока уведомлять
LESSON_START_NOTIFICATION_HOURS = 3      # За сколько часов до начала урока уведомлять
UNCONFIRMED_LESSON_TIMEOUT_HOURS = 1     # Через сколько часов помечать урок как неподтверждённый

# ===== НАСТРОЙКИ ОЧИСТКИ БД =====
OLD_DELETED_LESSONS_CLEANUP_DAYS = 14    # Удалять мягко-удалённые уроки старше N дней
OLD_COMPLETED_TASKS_CLEANUP_DAYS = 30    # Удалять завершённые задачи старше N дней

# ===== ПЕРИОДЫ СТАТИСТИКИ (дни) =====
STATS_MONTH_DAYS = 30                    # Период "за месяц"
STATS_HALF_YEAR_DAYS = 180               # Период "за полгода"
STATS_YEAR_DAYS = 365                    # Период "за год"
CHANGE_HISTORY_DAYS = 7                  # Период истории изменений

# ===== НАСТРОЙКИ УРОКОВ =====
LESSON_DURATIONS = [60, 90, 120]         # Доступные длительности уроков (минуты)
DEFAULT_LESSON_DURATION = 60             # Длительность по умолчанию

# ===== НАСТРОЙКИ СИСТЕМЫ ЗАДАЧ =====
SCHEDULED_TASK_MAX_RETRIES = 3           # Максимум повторных попыток для задач
SCHEDULED_TASK_FETCH_LIMIT = 20          # Размер batch при выборке задач
SCHEDULED_TASK_RETRY_DELAY_MINUTES = 5   # Задержка между повторными попытками
