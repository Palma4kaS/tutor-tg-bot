"""
Исполнитель задач для выполнения запланированных задач
"""
import json
import asyncio
import aiosqlite
from typing import Dict, Optional
from datetime import datetime, timedelta
from bot_template.database.db_manager import DatabaseManager
from bot_template.database.task_manager import TaskManager
from bot_template.utils.logger import get_logger

# Logger для этого модуля
logger = get_logger("task_executor")

# Импортируем функцию для получения локального времени и часовой пояс
try:
    from bot_template.config import get_local_time, MOSCOW_TZ, TUTOR_ID, OLD_COMPLETED_TASKS_CLEANUP_DAYS
except ImportError:
    from datetime import timezone, timedelta
    MOSCOW_TZ = timezone(timedelta(hours=3))
    TUTOR_ID = None
    OLD_COMPLETED_TASKS_CLEANUP_DAYS = 30
    def get_local_time():
        return datetime.now(MOSCOW_TZ)


class TaskExecutor:
    """Исполнитель задач - проверяет и выполняет запланированные задачи"""
    
    def __init__(self, db: DatabaseManager, bot=None):
        self.db = db
        self.bot = bot
        self.task_manager = TaskManager(db)
        self.max_retries = 3
        self.retry_delay_minutes = 5
    
    async def execute_task(self, task: Dict) -> bool:
        """
        Выполнить одну задачу
        
        Args:
            task: Словарь с данными задачи
        
        Returns:
            True если успешно, False если ошибка
        """
        task_id = task['id']
        task_type = task['task_type']
        execution_data_json = task.get('execution_data')
        retry_count = task.get('retry_count', 0)
        max_retries = task.get('max_retries', 3)
        
        try:
            # Парсим execution_data если есть
            execution_data = None
            if execution_data_json:
                execution_data = json.loads(execution_data_json)
            
            # Выполняем задачу в зависимости от типа
            success = False
            if task_type == 'lesson_ending_notification':
                success = await self._execute_ending_notification(task, execution_data)
            elif task_type == 'lesson_starting_notification':
                success = await self._execute_starting_notification(task, execution_data)
            elif task_type == 'lesson_start_notification':
                success = await self._execute_start_notification(task, execution_data)
            elif task_type == 'lesson_generation':
                success = await self._execute_generation(task)
            elif task_type == 'lesson_cleanup':
                success = await self._execute_cleanup(task)
            else:
                error_msg = f"Неизвестный тип задачи: {task_type}"
                await self.db.update_task_status(task_id, 'failed', error_msg)
                logger.error(error_msg)
                return False
            
            if success:
                # Помечаем задачу как выполненную
                await self.db.update_task_status(task_id, 'completed')
                logger.info(f"Задача #{task_id} ({task_type}) выполнена успешно")
                return True
            else:
                # Обработка ошибки
                if retry_count < max_retries:
                    # Планируем повторную попытку
                    new_time = (get_local_time() + timedelta(minutes=self.retry_delay_minutes)).strftime('%Y-%m-%d %H:%M:%S')
                    await self.db.increment_task_retry(task_id, new_time)
                    logger.warning(f"Задача #{task_id} ({task_type}) не выполнена, попытка {retry_count + 1}/{max_retries}")
                    return False
                else:
                    # Превышен лимит попыток
                    error_msg = f"Превышен лимит попыток ({max_retries})"
                    await self.db.update_task_status(task_id, 'failed', error_msg)
                    logger.error(f"Задача #{task_id} ({task_type}) провалена: {error_msg}")
                    return False
                    
        except Exception as e:
            error_msg = str(e)
            if retry_count < max_retries:
                new_time = (get_local_time() + timedelta(minutes=self.retry_delay_minutes)).strftime('%Y-%m-%d %H:%M:%S')
                await self.db.increment_task_retry(task_id, new_time)
                logger.warning(f"Ошибка выполнения задачи #{task_id} ({task_type}): {error_msg}, попытка {retry_count + 1}/{max_retries}")
            else:
                await self.db.update_task_status(task_id, 'failed', error_msg)
                logger.error(f"Задача #{task_id} ({task_type}) провалена: {error_msg}")
            return False
    
    async def _execute_ending_notification(self, task: Dict, execution_data: Optional[Dict]) -> bool:
        """Выполнить уведомление об окончании занятия"""
        if not self.bot or not execution_data:
            return False
        
        lesson_id = execution_data.get('lesson_id')
        if not lesson_id:
            return False
        
        # Получаем занятие с информацией об ученике
        async with aiosqlite.connect(self.db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT l.*, s.name as student_name
                FROM lessons l
                JOIN students s ON l.student_id = s.user_id
                WHERE l.id = ?
            """, (lesson_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return False
                lesson = dict(row)
        
        # Импортируем функцию из scheduler.py
        from bot_template.scheduler import send_lesson_ending_notification
        
        try:
            return await send_lesson_ending_notification(lesson, self.db, self.bot)
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления об окончании: {e}")
            return False
    
    async def _execute_starting_notification(self, task: Dict, execution_data: Optional[Dict]) -> bool:
        """Выполнить уведомление о начале занятия (за 3 часа)"""
        if not self.bot or not execution_data:
            return False
        
        lesson_id = execution_data.get('lesson_id')
        if not lesson_id:
            return False
        
        # Получаем занятие с информацией об ученике
        async with aiosqlite.connect(self.db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT l.*, s.name as student_name, s.user_id
                FROM lessons l
                JOIN students s ON l.student_id = s.user_id
                WHERE l.id = ?
            """, (lesson_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return False
                lesson = dict(row)
        
        # Импортируем функцию из scheduler.py
        from bot_template.scheduler import send_lesson_starting_notification
        
        try:
            return await send_lesson_starting_notification(lesson, self.db, self.bot)
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о начале: {e}")
            return False
    
    async def _execute_start_notification(self, task: Dict, execution_data: Optional[Dict]) -> bool:
        """Выполнить уведомление о факте начала занятия"""
        if not self.bot or not execution_data:
            return False
        
        lesson_id = execution_data.get('lesson_id')
        if not lesson_id:
            return False
        
        # Получаем занятие
        lesson = await self.db.get_lesson_by_id(lesson_id)
        if not lesson:
            return False
        
        # Импортируем функцию из handlers.py
        from bot_template.app.handlers import send_lesson_start_notification
        
        try:
            return await send_lesson_start_notification(lesson, self.bot, self.db)
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о факте начала: {e}")
            return False
    
    async def _execute_generation(self, task: Dict) -> bool:
        """Выполнить автогенерацию занятий"""
        # Импортируем функцию из scheduler.py
        from bot_template.scheduler import generate_lessons_from_schedules
        
        try:
            await generate_lessons_from_schedules(self.db)
            
            # Планируем следующую генерацию на завтра в 00:30
            await self.task_manager.schedule_generation_task()
            
            return True
        except Exception as e:
            logger.error(f"Ошибка автогенерации занятий: {e}")
            return False
    
    async def _execute_cleanup(self, task: Dict) -> bool:
        """Выполнить очистку старых занятий и задач"""
        # Импортируем функцию из scheduler.py
        from bot_template.scheduler import cleanup_old_deleted_lessons
        
        try:
            # Очищаем старые занятия
            await cleanup_old_deleted_lessons(self.db)
            
            # Очищаем старые выполненные задачи (старше 30 дней)
            deleted_tasks = await self.db.cleanup_old_completed_tasks(days=OLD_COMPLETED_TASKS_CLEANUP_DAYS)
            if deleted_tasks > 0:
                logger.info(f"Очищено {deleted_tasks} старых выполненных задач")
            
            # Планируем следующую очистку на завтра в 01:00
            await self.task_manager.schedule_cleanup_task()
            
            return True
        except Exception as e:
            logger.error(f"Ошибка очистки старых занятий: {e}")
            return False
    
    async def process_pending_tasks(self, batch_size: int = 20) -> Dict[str, int]:
        """
        Обработать задачи, готовые к выполнению
        
        Args:
            batch_size: Максимальное количество задач для обработки за раз
        
        Returns:
            Словарь со статистикой: {'processed': X, 'succeeded': Y, 'failed': Z}
        """
        tasks = await self.db.get_pending_tasks(limit=batch_size)
        
        if not tasks:
            return {'processed': 0, 'succeeded': 0, 'failed': 0}
        
        stats = {'processed': len(tasks), 'succeeded': 0, 'failed': 0}
        
        for task in tasks:
            success = await self.execute_task(task)
            if success:
                stats['succeeded'] += 1
            else:
                stats['failed'] += 1
        
        return stats

