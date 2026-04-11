"""
Менеджер задач для планирования уведомлений и системных задач
"""
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from bot_template.database.db_manager import DatabaseManager

# Импортируем функцию для получения локального времени и часовой пояс
try:
    from bot_template.config import get_local_time, MOSCOW_TZ
except ImportError:
    from datetime import timezone, timedelta
    MOSCOW_TZ = timezone(timedelta(hours=3))
    def get_local_time():
        return datetime.now(MOSCOW_TZ)


class TaskManager:
    """Менеджер для создания и управления запланированными задачами"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    async def schedule_lesson_tasks(self, lesson: Dict, days_ahead: int = 30) -> List[int]:
        """
        Создать все задачи для занятия на ближайшие N дней
        
        Args:
            lesson: Словарь с данными занятия
            days_ahead: На сколько дней вперед планировать (по умолчанию 30)
        
        Returns:
            Список ID созданных задач
        """
        task_ids = []
        lesson_id = lesson['id']
        lesson_date = lesson['lesson_date']
        lesson_time = lesson['lesson_time']
        duration = lesson.get('duration', 60)
        student_id = lesson.get('student_id')
        
        # Парсим дату и время начала занятия
        lesson_start_naive = datetime.strptime(
            f"{lesson_date} {lesson_time}",
            '%Y-%m-%d %H:%M'
        )
        lesson_start = lesson_start_naive.replace(tzinfo=MOSCOW_TZ)
        lesson_end = lesson_start + timedelta(minutes=duration)
        now = get_local_time()
        
        # Проверяем, что занятие в будущем и в пределах days_ahead дней
        days_until_lesson = (lesson_start.date() - now.date()).days
        if days_until_lesson < 0 or days_until_lesson > days_ahead:
            return task_ids  # Занятие в прошлом или слишком далеко
        
        # Подготовка данных для выполнения
        execution_data = {
            'lesson_id': lesson_id,
            'student_id': student_id,
            'lesson_date': lesson_date,
            'lesson_time': lesson_time
        }
        
        # 1. Задача: уведомление об окончании (за 5 минут до окончания)
        ending_notification_time = lesson_end - timedelta(minutes=5)
        if ending_notification_time > now:
            # Проверяем, нет ли уже такой задачи
            if not await self.db.task_exists(lesson_id, 'lesson_ending_notification'):
                task_id = await self.db.create_scheduled_task(
                    lesson_id=lesson_id,
                    task_type='lesson_ending_notification',
                    scheduled_time=ending_notification_time.strftime('%Y-%m-%d %H:%M:%S'),
                    execution_data=execution_data
                )
                task_ids.append(task_id)
        
        # 2. Задача: уведомление о начале (за 3 часа до начала)
        starting_notification_time = lesson_start - timedelta(hours=3)
        if starting_notification_time > now:
            # Проверяем, нет ли уже такой задачи
            if not await self.db.task_exists(lesson_id, 'lesson_starting_notification'):
                task_id = await self.db.create_scheduled_task(
                    lesson_id=lesson_id,
                    task_type='lesson_starting_notification',
                    scheduled_time=starting_notification_time.strftime('%Y-%m-%d %H:%M:%S'),
                    execution_data=execution_data
                )
                task_ids.append(task_id)
        
        # 3. Задача: уведомление о факте начала (в момент начала)
        if lesson_start > now:
            # Проверяем, нет ли уже такой задачи
            if not await self.db.task_exists(lesson_id, 'lesson_start_notification'):
                task_id = await self.db.create_scheduled_task(
                    lesson_id=lesson_id,
                    task_type='lesson_start_notification',
                    scheduled_time=lesson_start.strftime('%Y-%m-%d %H:%M:%S'),
                    execution_data=execution_data
                )
                task_ids.append(task_id)
        
        return task_ids
    
    async def cancel_lesson_tasks(self, lesson_id: int, task_types: Optional[List[str]] = None) -> int:
        """
        Отменить задачи для занятия
        
        Args:
            lesson_id: ID занятия
            task_types: Список типов задач для отмены (если None - отменить все)
        
        Returns:
            Количество отмененных задач
        """
        return await self.db.cancel_lesson_tasks(lesson_id, task_types)
    
    async def reschedule_lesson_tasks(self, lesson: Dict) -> List[int]:
        """
        Перепланировать задачи для занятия (отменить старые, создать новые)
        
        Args:
            lesson: Словарь с обновленными данными занятия
        
        Returns:
            Список ID созданных задач
        """
        lesson_id = lesson['id']
        
        # Отменяем все старые задачи
        await self.cancel_lesson_tasks(lesson_id)
        
        # Создаем новые задачи
        return await self.schedule_lesson_tasks(lesson)
    
    async def schedule_generation_task(self, scheduled_time: Optional[str] = None) -> int:
        """
        Запланировать задачу автогенерации занятий
        
        Args:
            scheduled_time: Время выполнения (если None - завтра в 00:30)
        
        Returns:
            ID созданной задачи
        """
        if scheduled_time is None:
            tomorrow = get_local_time().date() + timedelta(days=1)
            scheduled_time = datetime.combine(tomorrow, datetime.min.time().replace(hour=0, minute=30))
            scheduled_time = scheduled_time.replace(tzinfo=MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S')
        
        # Проверяем, нет ли уже такой задачи
        if not await self.db.task_exists(None, 'lesson_generation'):
            return await self.db.create_scheduled_task(
                lesson_id=None,
                task_type='lesson_generation',
                scheduled_time=scheduled_time,
                execution_data=None
            )
        return 0
    
    async def schedule_cleanup_task(self, scheduled_time: Optional[str] = None) -> int:
        """
        Запланировать задачу очистки старых занятий
        
        Args:
            scheduled_time: Время выполнения (если None - завтра в 01:00)
        
        Returns:
            ID созданной задачи
        """
        if scheduled_time is None:
            tomorrow = get_local_time().date() + timedelta(days=1)
            scheduled_time = datetime.combine(tomorrow, datetime.min.time().replace(hour=1, minute=0))
            scheduled_time = scheduled_time.replace(tzinfo=MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S')
        
        # Проверяем, нет ли уже такой задачи
        if not await self.db.task_exists(None, 'lesson_cleanup'):
            return await self.db.create_scheduled_task(
                lesson_id=None,
                task_type='lesson_cleanup',
                scheduled_time=scheduled_time,
                execution_data=None
            )
        return 0

