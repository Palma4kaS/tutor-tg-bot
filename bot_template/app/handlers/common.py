from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton,
                          InlineKeyboardMarkup, InlineKeyboardButton)

import aiosqlite
from datetime import datetime, timedelta
from typing import Dict
from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
import os

from config import ADMINS_IDS, TUTOR_ID, DB_PATH, ONLINE, OFFLINE, PROFIL, CLASS_10_11, CLASS_9
from bot_template.config import get_local_time, MOSCOW_TZ
from bot_template.utils.logger import get_logger
from bot_template.utils.formatting import (
    WEEKDAYS_RU, WEEKDAYS_RU_FULL,
    format_date_with_weekday, format_lesson_time,
    format_duration_short, format_duration_label,
    format_time_range, format_lesson_word,
)

import bot_template.app.keyboards as kb

# Logger для этого модуля
logger = get_logger("handlers")

async def send_schedule_change_notification(bot: Bot, student_id: int, old_schedule: Dict, new_schedule: Dict):
    """
    Отправить уведомление ученику об изменении расписания
    """
    try:
        weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        format_names = {"online": "Онлайн", "offline": "Очно"}

        lines = []

        # День недели - всегда показываем
        old_weekday = old_schedule.get('weekday', 0)
        new_weekday = new_schedule.get('weekday', 0)
        old_day = weekday_names[old_weekday]
        new_day = weekday_names[new_weekday]
        if old_weekday != new_weekday:
            lines.append(f"📅 День недели: {old_day} → {new_day}")
        else:
            lines.append(f"📅 День недели: {new_day}")

        # Время - всегда показываем
        old_time = old_schedule.get('time', '')
        new_time = new_schedule.get('time', '')
        if old_time != new_time:
            lines.append(f"🕐 Время: {old_time} → {new_time}")
        else:
            lines.append(f"🕐 Время: {new_time}")

        # Продолжительность - всегда показываем
        old_duration = old_schedule.get('duration', 60)
        new_duration = new_schedule.get('duration', 60)
        old_dur_text = f"{old_duration//60}ч" if old_duration >= 60 else f"{old_duration}м"
        if old_duration == 90:
            old_dur_text = "1.5ч"
        new_dur_text = f"{new_duration//60}ч" if new_duration >= 60 else f"{new_duration}м"
        if new_duration == 90:
            new_dur_text = "1.5ч"
        if old_duration != new_duration:
            lines.append(f"⏱️ Продолжительность: {old_dur_text} → {new_dur_text}")
        else:
            lines.append(f"⏱️ Продолжительность: {new_dur_text}")

        # Формат - всегда показываем
        old_format_value = old_schedule.get('lesson_format', 'online')
        new_format_value = new_schedule.get('lesson_format', 'online')
        old_format = format_names.get(old_format_value, 'Онлайн')
        new_format = format_names.get(new_format_value, 'Онлайн')
        if old_format_value != new_format_value:
            lines.append(f"📍 Формат: {old_format} → {new_format}")
        else:
            lines.append(f"📍 Формат: {new_format}")

        # Стоимость - всегда показываем
        old_price = int(old_schedule.get('price', 0))
        new_price = int(new_schedule.get('price', 0))
        if old_price != new_price:
            lines.append(f"💰 Стоимость: {old_price}₽ → {new_price}₽")
        else:
            lines.append(f"💰 Стоимость: {new_price}₽")

        # Отправляем уведомление со всеми параметрами
        message_text = "🔔 Обновление расписания\n\n"
        message_text += "Ваше расписание было изменено:\n\n"
        message_text += "\n".join(lines)

        await bot.send_message(
            chat_id=student_id,
            text=message_text
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления об изменении расписания: {e}")

# Добавляем путь к корневой папке проекта
# current_dir = os.path.dirname(os.path.abspath(__file__))
# template_dir = os.path.join(current_dir, '..')
# root_dir = os.path.dirname(os.path.dirname(current_dir))
# sys.path.insert(0, root_dir)

# Получаем имя папки tutor (tutor_xxxxxxx) из .env

# Строим абсолютный путь к базе в tutors/tutor_xxxxxxx/


from bot_template.database.db_manager import DatabaseManager
db = DatabaseManager(db_path=DB_PATH)

router = Router()

class AdminPanelStates(StatesGroup):
    panel = State()
    searching_student = State()
    # Новые состояния для расписания
    schedule_management = State()
    creating_schedule_weekday = State()
    creating_schedule_time = State()
    creating_schedule_format = State()
    creating_schedule_price = State()
    creating_schedule_confirmation = State()
    # Состояния для управления занятиями
    lesson_management = State()
    rescheduling_date = State()
    rescheduling_time = State()
    entering_reschedule_custom_time = State()
    editing_schedule_day = State()
    editing_schedule_time = State()
    editing_schedule_format = State()
    editing_schedule_price = State()
     # Добавляем новые состояния
    creating_schedule_duration = State()
    creating_schedule_custom_duration = State()

    # Состояния для редактирования продолжительности
    editing_schedule_duration = State()
    editing_schedule_custom_duration = State()

    # Состояния для редактирования профиля ученика учителем
    editing_student_name = State()
    editing_student_grade = State()
    editing_student_subject = State()

    # Состояния для работы с занятиями
    lesson_ending_feedback = State()
    adding_homework = State()
    adding_homework_photo = State()
    editing_homework = State()

    # Состояния для создания занятия вне расписания
    creating_lesson_student = State()
    creating_lesson_date = State()
    creating_lesson_time = State()
    creating_lesson_format = State()
    creating_lesson_duration = State()
    creating_lesson_custom_duration = State()
    creating_lesson_price = State()

    # Состояния для настройки цен
    setting_price_base = State()
    setting_price_online = State()
    setting_price_grade_9 = State()
    setting_price_grade_10_11 = State()
    setting_price_profile = State()
    editing_price_setting = State()

    # Состояние для индивидуальной цены ученика
    setting_student_custom_price = State()


class Reg(StatesGroup):
    userFormat = State()
    userClass = State()
    userVar = State()
    userName = State()
    userNumber = State()
    feedback = State()

    change_name = State()
    change_grade = State()
    change_subject = State()

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS_IDS

async def check_admin_access(message: Message) -> bool:
    if not is_admin(message.from_user.id):
        #await message.answer("⛔️ Нет доступа к админ-панели.")
        return False
    return True

async def send_lesson_start_notification(lesson: Dict, bot_instance: Bot, db_instance: DatabaseManager) -> bool:
    """Отправить учителю сообщение о начале занятия (если ещё не отправляли)"""
    if lesson.get('start_notification_sent_at'):
        return False

    student_id = lesson.get('student_id')
    if not student_id:
        return False

    student = await db_instance.get_student(student_id)
    if not student:
        return False

    student_name = student.get('name') or student.get('username') or "Ученик"
    duration_minutes = lesson.get('duration') or 60
    time_range = format_time_range(lesson['lesson_time'], duration_minutes)
    duration_label = format_duration_label(duration_minutes)
    homework_text = (lesson.get('homework') or '').strip()
    debt_info = await db_instance.get_student_debt(student_id)
    total_debt = int(round(debt_info.get('total_debt', 0)))
    unpaid_count = int(debt_info.get('unpaid_count', 0))

    message_lines = [
        "🟢 Занятие",
        f"🕑 {time_range}",
        f"👤 Ученик: {student_name}",
        f"⏱️ Длительность: {duration_label}"
    ]

    if homework_text:
        message_lines.append(f"🧭 Домашнее задание: {homework_text}")

    if total_debt > 0:
        debt_amount = f"{total_debt:,}".replace(",", " ")
        lesson_word = format_lesson_word(unpaid_count or 1)
        message_lines.append(f"💰 Задолженность: {debt_amount}₽ ({unpaid_count} {lesson_word})")

    notification_text = "\n".join(message_lines)

    try:
        await bot_instance.send_message(chat_id=TUTOR_ID, text=notification_text)
        timestamp = get_local_time().strftime('%Y-%m-%d %H:%M:%S')
        await db_instance.update_lesson_start_notification(lesson['id'], timestamp)
        logger.info(f"Отправлено уведомление учителю о начале занятия ученика {student_name}")
        return True
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление о начале занятия: {e}")
        return False

async def check_admin_access_callback(callback: CallbackQuery) -> bool:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа к админ-панели.", show_alert=True)
        return False
    return True

async def safe_callback_answer(callback: CallbackQuery, text: str = None, show_alert: bool = False):
    """
    Безопасный ответ на callback query с обработкой ошибки истекшего query.
    Игнорирует ошибку "query is too old and response timeout expired".
    """
    try:
        await callback.answer(text=text, show_alert=show_alert)
    except TelegramBadRequest as e:
        if "query is too old" in str(e) or "query ID is invalid" in str(e):
            # Игнорируем ошибку истекшего query - это нормально при перезапуске бота
            pass
        else:
            # Пробрасываем другие ошибки
            raise
