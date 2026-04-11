"""
Логика планировщика: генерация занятий, уведомления, очистка.

Все функции, ранее жившие в run.py и вызываемые по расписанию
через APScheduler, собраны здесь.
"""

import aiosqlite
from datetime import datetime, timedelta
from typing import Dict

from bot_template.utils.logger import get_logger
from bot_template.utils.formatting import format_date_with_weekday

try:
    from config import TUTOR_ID, DB_PATH
    from bot_template.config import (
        get_local_time, MOSCOW_TZ,
        LESSON_END_NOTIFICATION_MINUTES,
        LESSON_START_NOTIFICATION_HOURS,
        OLD_DELETED_LESSONS_CLEANUP_DAYS,
        OLD_COMPLETED_TASKS_CLEANUP_DAYS,
    )
except ImportError:
    from datetime import timezone
    MOSCOW_TZ = timezone(timedelta(hours=3))
    TUTOR_ID = None
    DB_PATH = None
    LESSON_END_NOTIFICATION_MINUTES = 5
    LESSON_START_NOTIFICATION_HOURS = 3
    OLD_DELETED_LESSONS_CLEANUP_DAYS = 14
    OLD_COMPLETED_TASKS_CLEANUP_DAYS = 30
    def get_local_time():
        return datetime.now(MOSCOW_TZ)

logger = get_logger("scheduler")


async def generate_lessons_from_schedules(db_instance):
    """Автогенерация занятий по расписаниям на 4 недели вперед"""
    try:
        schedules = await db_instance.get_active_schedules()
        created_count = 0
        skipped_exists = 0
        skipped_deleted = 0

        # Импортируем TaskManager для создания задач
        from bot_template.database.task_manager import TaskManager
        task_manager = TaskManager(db_instance)

        for schedule in schedules:
            next_dates = get_next_lesson_dates(schedule['weekday'], weeks=4)

            for lesson_date in next_dates:
                # Проверяем, существует ли активное занятие
                if await db_instance.lesson_exists(schedule['student_id'], lesson_date, schedule['time']):
                    skipped_exists += 1
                    continue

                # Проверяем, было ли занятие удалено вручную
                if await db_instance.lesson_was_manually_deleted_from_schedule(schedule['id'], lesson_date):
                    skipped_deleted += 1
                    logger.debug(f"Пропуск: занятие {lesson_date} {schedule['time']} было удалено вручную")
                    continue

                # Создаём новое занятие
                lesson_id = await db_instance.create_lesson_from_schedule(schedule['id'], lesson_date)
                if lesson_id:
                    created_count += 1

                    # Создаем задачи уведомлений для нового занятия
                    try:
                        lesson = await db_instance.get_lesson_by_id(lesson_id)
                        if lesson:
                            await task_manager.schedule_lesson_tasks(lesson, days_ahead=30)
                    except Exception as task_error:
                        logger.warning(f"Ошибка создания задач для занятия #{lesson_id}: {task_error}")

        logger.info(f"Автогенерация занятий выполнена: {get_local_time().strftime('%Y-%m-%d %H:%M')}")
        logger.info(f"Создано: {created_count}, пропущено (существуют): {skipped_exists}, пропущено (удалены): {skipped_deleted}")

    except Exception as e:
        logger.error(f"Ошибка автогенерации: {e}")


async def send_lesson_ending_notification(lesson: dict, db_instance, bot_instance) -> bool:
    """Отправить уведомление об окончании занятия для конкретного занятия"""
    try:
        # Проверяем, что занятие еще не завершено
        if lesson.get('status') != 'scheduled':
            return False

        # Проверяем, не отправляли ли уже уведомление
        if lesson.get('ending_notification_sent_at'):
            return True  # Уже отправлено

        # Формируем сообщение учителю
        date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)

        duration_hours = lesson['duration'] // 60
        duration_mins = lesson['duration'] % 60
        duration_str = f"{duration_hours}ч {duration_mins}мин" if duration_mins else f"{duration_hours}ч"

        payment_emoji = "💰" if lesson['payment_status'] == 'paid' else "❌"
        payment_text = "оплачено" if lesson['payment_status'] == 'paid' else "не оплачено"

        # Определяем, сколько минут осталось до окончания
        lesson_start_naive = datetime.strptime(
            f"{lesson['lesson_date']} {lesson['lesson_time']}",
            '%Y-%m-%d %H:%M'
        )
        lesson_start = lesson_start_naive.replace(tzinfo=MOSCOW_TZ)
        duration = lesson.get('duration', 60)
        lesson_end = lesson_start + timedelta(minutes=duration)
        now = get_local_time()
        minutes_left = int((lesson_end - now).total_seconds() / 60)

        if minutes_left <= 0:
            time_text = "Занятие завершается!"
        elif minutes_left == 1:
            time_text = "Занятие завершается через 1 минуту!"
        else:
            time_text = f"Занятие завершается через {minutes_left} минуты!"

        # Форматируем время окончания
        lesson_end_time = lesson_end.strftime('%H:%M')

        message = (
            f"⏰ {time_text}\n\n"
            f"👤 Ученик: {lesson['student_name']}\n"
            f"📅 {date_str} в {lesson['lesson_time']}\n"
            f"⏱️ Продолжительность: {duration_str}\n"
            f"🕐 Окончание: {lesson_end_time}\n"
            f"{payment_emoji} Оплата: {payment_text}\n\n"
            f"📝 Не забудьте отметить статус оплаты и задать домашнее задание!"
        )

        # Импортируем клавиатуру из keyboards.py
        from bot_template.app.keyboards import lesson_ending_keyboard

        await bot_instance.send_message(
            chat_id=TUTOR_ID,
            text=message,
            reply_markup=lesson_ending_keyboard(lesson['id'], lesson.get('student_id'))
        )

        # Отмечаем, что уведомление отправлено
        notification_time = get_local_time().strftime('%Y-%m-%d %H:%M:%S')
        await db_instance.update_lesson_ending_notification(lesson['id'], notification_time)

        logger.info(f"Отправлено уведомление учителю о занятии #{lesson['id']} (ученик: {lesson['student_name']})")
        return True

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об окончании для занятия #{lesson.get('id')}: {e}")
        return False


async def check_ending_lessons(db_instance, bot_instance):
    """Проверка занятий, заканчивающихся в ближайшие 0-5 минут - уведомление учителю"""
    try:
        lessons = await db_instance.get_lessons_ending_soon(minutes_before=LESSON_END_NOTIFICATION_MINUTES, debug=False)

        if lessons:
            logger.debug(f"Найдено {len(lessons)} занятий, заканчивающихся в ближайшие 0-5 минут")
        else:
            logger.debug("Проверка завершена: занятий, заканчивающихся в ближайшие 0-5 минут, не найдено")

        for lesson in lessons:
            await send_lesson_ending_notification(lesson, db_instance, bot_instance)

    except Exception as e:
        logger.error(f"Ошибка проверки завершающихся занятий: {e}")
        logger.exception("Traceback:")


async def check_lessons_24h_before(db_instance, bot_instance):
    """Проверка занятий, начинающихся через 24 часа - уведомления ученикам с домашним заданием"""
    # Временно отключено
    return


async def check_lesson_start_notifications(db_instance, bot_instance):
    """Проверка факта начала занятия — уведомление учителю"""
    try:
        from bot_template.app.handlers import send_lesson_start_notification

        today_str = get_local_time().strftime('%Y-%m-%d')
        lessons = await db_instance.get_lessons_without_start_notification(today_str)
        if not lessons:
            return

        now = get_local_time()
        for lesson in lessons:
            try:
                lesson_start_naive = datetime.strptime(
                    f"{lesson['lesson_date']} {lesson['lesson_time']}",
                    '%Y-%m-%d %H:%M'
                )
                lesson_start = lesson_start_naive.replace(tzinfo=MOSCOW_TZ)
            except Exception as parse_error:
                logger.warning(f"Не удалось разобрать время начала занятия #{lesson.get('id')}: {parse_error}")
                continue

            if now >= lesson_start:
                await send_lesson_start_notification(lesson, bot_instance, db_instance)
    except Exception as e:
        logger.error(f"Ошибка проверки начала занятий: {e}")


async def send_lesson_starting_notification(lesson: dict, db_instance, bot_instance) -> bool:
    """Отправить уведомление о начале занятия (за 3 часа) для конкретного занятия"""
    try:
        student_id = lesson['user_id']

        # Проверяем, отправляли ли уже уведомление с кнопкой подтверждения
        if lesson.get('confirmation_sent_at'):
            return True  # Уже отправлено

        # Получаем задолженность ученика
        debt_info = await db_instance.get_student_debt(student_id)

        # Формируем сообщение ученику
        date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)

        duration_hours = lesson['duration'] // 60
        duration_mins = lesson['duration'] % 60
        duration_str = f"{duration_hours}ч {duration_mins}мин" if duration_mins else f"{duration_hours}ч"

        student_message = (
            f"📚 Напоминание о занятии\n\n"
            f"📅 {date_str} в {lesson['lesson_time']}\n"
            f"⏱️ Продолжительность: {duration_str}\n"
            f"📍 Формат: {'онлайн' if lesson['lesson_format'] == 'online' else 'оффлайн'}\n"
        )

        # Добавляем информацию о долге
        if debt_info['total_debt'] > 0:
            student_message += (
                f"\n💰 Задолженность: {debt_info['total_debt']:.0f}₽ "
                f"за {debt_info['unpaid_count']} занятий\n"
            )

        # Добавляем домашнее задание, если есть
        if lesson.get('homework'):
            hw_status = lesson.get('homework_status', 'assigned')
            hw_emoji = "✅" if hw_status == 'completed' else "📖"
            student_message += f"\n{hw_emoji} Домашнее задание: {lesson['homework']}\n"

        # Импортируем клавиатуру для подтверждения
        from bot_template.app.keyboards import lesson_confirmation_keyboard

        await bot_instance.send_message(
            chat_id=student_id,
            text=student_message,
            reply_markup=lesson_confirmation_keyboard(lesson['id'])
        )

        # Отмечаем, что уведомление отправлено
        confirmation_sent_at = get_local_time().strftime('%Y-%m-%d %H:%M:%S')
        await db_instance.update_lesson_confirmation(
            lesson['id'],
            None,  # Статус пока не определен
            confirmation_sent_at
        )

        logger.info(f"Отправлено напоминание с кнопкой подтверждения ученику {lesson['student_name']} (ID: {student_id})")

        # Уведомляем учителя о должнике
        if debt_info['total_debt'] > 0:
            teacher_message = (
                f"⚠️ У ученика {lesson['student_name']} задолженность:\n"
                f"💰 {debt_info['total_debt']:.0f}₽ за {debt_info['unpaid_count']} занятий\n"
                f"⏰ Занятие сегодня в {lesson['lesson_time']}"
            )

            await bot_instance.send_message(
                chat_id=TUTOR_ID,
                text=teacher_message
            )
            logger.info(f"Отправлено уведомление учителю о долге ученика {lesson['student_name']}")

        return True

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о начале для занятия #{lesson.get('id')}: {e}")
        return False


async def check_starting_lessons(db_instance, bot_instance):
    """Проверка занятий, начинающихся через 3 часа - уведомления ученикам с кнопкой подтверждения"""
    try:
        lessons = await db_instance.get_lessons_starting_soon(hours_before=LESSON_START_NOTIFICATION_HOURS)

        if lessons:
            logger.debug(f"Найдено {len(lessons)} занятий для проверки за 3 часа")

        for lesson in lessons:
            await send_lesson_starting_notification(lesson, db_instance, bot_instance)

    except Exception as e:
        logger.error(f"Ошибка проверки начинающихся занятий: {e}")


async def check_unconfirmed_lessons(db_instance, bot_instance):
    """Проверка неподтвержденных занятий - напоминание ученикам, которые не подтвердили участие"""
    try:
        lessons = await db_instance.get_unconfirmed_lessons()

        for lesson in lessons:
            student_id = lesson['user_id']

            # Формируем напоминание
            date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)

            duration_hours = lesson['duration'] // 60
            duration_mins = lesson['duration'] % 60
            duration_str = f"{duration_hours}ч {duration_mins}мин" if duration_mins else f"{duration_hours}ч"

            reminder_message = (
                f"⏰ Напоминание о занятии\n\n"
                f"📅 {date_str} в {lesson['lesson_time']}\n"
                f"⏱️ Продолжительность: {duration_str}\n"
                f"📍 Формат: {'онлайн' if lesson['lesson_format'] == 'online' else 'оффлайн'}\n\n"
                f"❗ Пожалуйста, подтвердите ваше участие"
            )

            # Импортируем клавиатуру для подтверждения
            from bot_template.app.keyboards import lesson_confirmation_keyboard

            try:
                await bot_instance.send_message(
                    chat_id=student_id,
                    text=reminder_message,
                    reply_markup=lesson_confirmation_keyboard(lesson['id'])
                )
                logger.info(f"Отправлено напоминание о неподтвержденном занятии ученику {lesson['student_name']} (ID: {student_id})")
            except Exception as e:
                logger.warning(f"Не удалось отправить напоминание ученику {student_id}: {e}")

    except Exception as e:
        logger.error(f"Ошибка проверки неподтвержденных занятий: {e}")


async def cleanup_old_deleted_lessons(db_instance):
    """Очистка старых мягко удаленных занятий (старше 2 недель)"""
    try:
        deleted_count = await db_instance.cleanup_old_deleted_lessons(days=OLD_DELETED_LESSONS_CLEANUP_DAYS)
        if deleted_count > 0:
            logger.info(f"Автоочистка: удалено {deleted_count} старых занятий (старше 2 недель)")
        else:
            logger.debug("Автоочистка: старых занятий для удаления не найдено")
    except Exception as e:
        logger.error(f"Ошибка автоочистки старых занятий: {e}")


async def migrate_existing_lessons_to_tasks(db_instance):
    """Миграция существующих занятий: создание задач для ближайших 30 дней"""
    try:
        from bot_template.database.task_manager import TaskManager
        task_manager = TaskManager(db_instance)

        # Получаем все запланированные занятия на ближайшие 30 дней
        today = get_local_time().date()
        end_date = today + timedelta(days=30)
        today_str = today.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

        async with aiosqlite.connect(db_instance.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT l.*, s.name as student_name
                FROM lessons l
                JOIN students s ON l.student_id = s.user_id
                WHERE l.lesson_date >= ? AND l.lesson_date <= ?
                AND l.status = 'scheduled'
                AND (l.is_manually_deleted = 0 OR l.is_manually_deleted IS NULL)
            """, (today_str, end_date_str)) as cursor:
                lessons = [dict(row) for row in await cursor.fetchall()]

        created_tasks = 0
        for lesson in lessons:
            try:
                task_ids = await task_manager.schedule_lesson_tasks(lesson, days_ahead=30)
                created_tasks += len(task_ids)
            except Exception as e:
                logger.warning(f"Ошибка создания задач для занятия #{lesson.get('id')}: {e}")

        logger.info(f"Миграция завершена: создано {created_tasks} задач для {len(lessons)} занятий")
        return created_tasks

    except Exception as e:
        logger.error(f"Ошибка миграции занятий: {e}")
        logger.exception("Traceback:")
        return 0


def get_next_lesson_dates(weekday: int, weeks: int = 4) -> list:
    """Получить даты следующих занятий по дню недели"""
    today = get_local_time()
    dates = []

    days_ahead = weekday - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7

    next_date = today + timedelta(days=days_ahead)

    for i in range(weeks):
        dates.append(next_date.strftime('%Y-%m-%d'))
        next_date += timedelta(weeks=1)

    return dates
