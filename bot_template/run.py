import asyncio
import sys
import os
from functools import partial

# Настройка путей
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, root_dir)

# Импортируем и инициализируем логгер
from bot_template.utils.logger import setup_logging, get_logger

# Импортируем функцию для получения локального времени и часовой пояс
try:
    from config import get_local_time, MOSCOW_TZ, BOT_TOKEN, TUTOR_ID, DB_PATH
except ImportError:
    # Если импорт не удался, используем datetime.now() как fallback
    from datetime import datetime, timezone, timedelta
    MOSCOW_TZ = timezone(timedelta(hours=3))
    BOT_TOKEN = None
    TUTOR_ID = None
    DB_PATH = None
    def get_local_time():
        return datetime.now(MOSCOW_TZ)

# Получаем tutor_id для логов из переменной окружения
tutor_folder = os.environ.get('TUTOR_FOLDER', 'bot_template')
logs_dir = os.path.join(current_dir, 'logs')
setup_logging(log_dir=logs_dir, tutor_id=tutor_folder)
logger = get_logger("run")

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bot_template.app.handlers import router
from bot_template.database.db_manager import DatabaseManager
from bot_template.database.task_manager import TaskManager
from bot_template.database.task_executor import TaskExecutor
from bot_template.scheduler import (
    generate_lessons_from_schedules,
    check_unconfirmed_lessons,
    migrate_existing_lessons_to_tasks,
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def main():
    # Создаем основной экземпляр БД для хендлеров
    main_db = DatabaseManager(db_path=DB_PATH)
    await main_db.init_db()
    logger.info(f"База данных инициализирована: {DB_PATH}")
    logger.info(f"ID репетитора: {TUTOR_ID}")

    # Подключаем роутер
    dp.include_router(router)

    # Создаем отдельный экземпляр БД для планировщика
    scheduler_db = DatabaseManager(db_path=DB_PATH)
    await scheduler_db.init_db()  # Убеждаемся, что он тоже инициализирован
    
    # Создаем TaskManager и TaskExecutor
    task_manager = TaskManager(scheduler_db)
    task_executor = TaskExecutor(scheduler_db, bot)
    
    # Миграция существующих занятий: создание задач для ближайших 30 дней
    logger.info("Выполняем миграцию существующих занятий...")
    await migrate_existing_lessons_to_tasks(scheduler_db)
    
    # Планируем задачи генерации и очистки
    await task_manager.schedule_generation_task()
    await task_manager.schedule_cleanup_task()
    
    # Настройка планировщика
    scheduler = AsyncIOScheduler()
    
    # Оставляем генерацию занятий по расписанию (cron) как резервный вариант
    scheduler.add_job(
        partial(generate_lessons_from_schedules, scheduler_db),
        'cron', 
        hour=0, 
        minute=30,
        id='lesson_generator'
    )
    
    # Основная проверка задач: каждые 60 секунд
    scheduler.add_job(
        partial(task_executor.process_pending_tasks, batch_size=20),
        'interval',
        seconds=60,
        id='process_scheduled_tasks'
    )
    
    # Оставляем проверку неподтвержденных занятий (не связано с конкретными занятиями)
    scheduler.add_job(
        partial(check_unconfirmed_lessons, scheduler_db, bot),
        'interval',
        hours=1,
        id='check_unconfirmed_lessons'
    )
    
    scheduler.start()
    logger.info("Планировщик автогенерации занятий запущен")
    logger.info("Система задач запущена (проверка каждые 60 секунд)")
    logger.info("Планировщик автоочистки старых занятий запущен")

    # Первичная генерация при старте
    logger.info("Выполняем первичную генерацию занятий...")
    await generate_lessons_from_schedules(scheduler_db)

    logger.info("Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")