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

    # Состояние для ввода кастомного времени при переносе
    entering_reschedule_custom_time = State()


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

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start с проверкой регистрации"""
    user_id = message.from_user.id

    # Проверяем, является ли пользователь учителем
    if await check_admin_access(message):
        await message.answer(
            f"👨‍🏫 Добро пожаловать, учитель!\n\n"
            f"Выберите действие из меню ниже:",
            reply_markup=kb.admin_main
        )
        return

    # Проверяем, зарегистрирован ли пользователь
    student = await db.get_student(user_id)

    if student:
        # Пользователь уже зарегистрирован
        await message.reply(
            f"👋 Добро пожаловать обратно, {student['username']}!\n\n"
            "Используйте меню ниже для выбора действий.",
            reply_markup=kb.main
        )
    else:
        # Пользователь не зарегистрирован
        await message.answer(
            "👋 Привет! Давай познакомимся!\n\n"
            "Нажми на кнопку ниже, чтобы узнать цену занятий 👇",
            reply_markup=kb.first_time_user
        )

@router.message(Command("pn"))
async def show_admin_panel(message: Message, state: FSMContext):
    if not await check_admin_access(message):
        return
    
    await state.set_state(AdminPanelStates.panel)
    await message.answer(
        "<b>👨‍🏫 С возвращением!</b>\n\n"
        f"Выберите действие из меню ниже:",
        reply_markup=kb.admin_main,
        parse_mode="HTML"
    )

@router.message(F.text == "👥 Мои ученики")
async def show_students(message: Message):
    # Проверка прав
    if not await check_admin_access(message):
        return
    
    students = await db.get_all_students()
    total_count = len(students)
    
    if total_count == 0:
        await message.answer(
            "📚 У вас пока нет зарегистрированных учеников.\n\n"
            "Когда кто-то зарегистрируется, он появится здесь!",
            reply_markup=kb.admin_main
        )
        return
    
    # Генерируем клавиатуру со списком
    keyboard = kb.generate_students_list(students)
    
    await message.answer(
        f"      📚 СПИСОК УЧЕНИКОВ ({total_count})\n\n"
        f"Выберите ученика для просмотра профиля:",
        reply_markup=keyboard
    )

async def show_new_students_internal(event, is_callback: bool = False):
    """Внутренняя функция для показа списка новых учеников"""
    students = await db.get_new_students()
    total_count = len(students)
    
    if total_count == 0:
        text = (
            "✅ <b>Все ученики просмотрены!</b>\n\n"
            "Новые ученики появятся здесь после регистрации и будут показаны до тех пор, пока вы не откроете их профиль."
        )
        if is_callback:
            await event.message.edit_text(text, reply_markup=kb.admin_main, parse_mode="HTML")
            await event.answer()
        else:
            await event.answer(text, reply_markup=kb.admin_main, parse_mode="HTML")
        return
    
    # Генерируем клавиатуру со списком новых учеников
    keyboard = kb.generate_students_list(students, is_new_students=True)
    
    text = (
        f"      🆕 НОВЫЕ УЧЕНИКИ ({total_count})\n\n"
        f"Показаны только непросмотренные ученики, отсортированные по дате регистрации (от старых к новым):"
    )
    
    if is_callback:
        await event.message.edit_text(text, reply_markup=keyboard)
        await event.answer()
    else:
        await event.answer(text, reply_markup=keyboard)

@router.message(F.text == "🆕 Новые ученики")
async def show_new_students(message: Message):
    """Показать список новых учеников, отсортированных по дате регистрации"""
    # Проверка прав
    if not await check_admin_access(message):
        return
    
    await show_new_students_internal(message, is_callback=False)

@router.callback_query(F.data == "show_new_students")
async def show_new_students_callback(callback: CallbackQuery):
    """Обработчик callback для возврата к списку новых учеников"""
    if not await check_admin_access_callback(callback):
        return
    
    await show_new_students_internal(callback, is_callback=True)

@router.message(F.text == "⚙️ Настройки")
async def show_settings(message: Message, state: FSMContext):
    """Показать настройки цен"""
    if not await check_admin_access(message):
        return
    
    settings = await db.get_price_settings()
    
    if not settings:
        # Первая настройка - запрашиваем базовую цену
        await state.set_state(AdminPanelStates.setting_price_base)
        await message.answer(
            "⚙️ <b>НАСТРОЙКА ЦЕН</b>\n\n"
            "Начнем с базовой цены:\n"
            "💰 Введите базовую цену за час (для 5-8 класс, база, очно):\n\n"
            "Например: <b>1000</b>",
            parse_mode="HTML",
            reply_markup=kb.back_to_admin_button()
        )
    else:
        # Показываем текущие настройки и таблицу цен
        combinations = db.get_all_price_combinations(settings)
        
        text = "⚙️ <b>НАСТРОЙКИ ЦЕН</b>\n\n"
        text += "<b>Текущие параметры:</b>\n"
        text += f"• Базовая цена: {int(settings['base_price'])}₽/час\n"
        text += f"• Надбавка за онлайн: +{int(settings['online_surcharge'])}₽\n"
        text += f"• Надбавка за 9 класс: +{int(settings['grade_9_surcharge'])}₽\n"
        text += f"• Надбавка за 10-11 класс: +{int(settings['grade_10_11_surcharge'])}₽\n"
        text += f"• Надбавка за профиль: +{int(settings['profile_surcharge'])}₽\n\n"
        text += "<b>📊 Таблица цен:</b>\n"
        
        for combo in combinations:
            text += f"• {combo['grade_range']}, {combo['subject']}, {combo['format']}: {int(combo['price'])}₽/час\n"
        
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=kb.price_settings_keyboard(has_settings=True)
        )

# === ОБРАБОТЧИКИ НАСТРОЙКИ ЦЕН ===

@router.message(AdminPanelStates.setting_price_base)
async def process_price_base(message: Message, state: FSMContext):
    """Обработка базовой цены"""
    if not await check_admin_access(message):
        await state.clear()
        return
    
    try:
        price = float(message.text.strip().replace(',', '.'))
        if price <= 0:
            raise ValueError
        
        await state.update_data(base_price=price)
        await state.set_state(AdminPanelStates.setting_price_online)
        await message.answer(
            f"✅ Базовая цена: <b>{int(price)}₽/час</b>\n\n"
            f"💰 Введите надбавку за онлайн формат:\n\n"
            f"Например: <b>200</b>",
            parse_mode="HTML",
            reply_markup=kb.back_to_admin_button()
        )
    except ValueError:
        await message.answer("❌ Введите корректную цену (положительное число)")

@router.message(AdminPanelStates.setting_price_online)
async def process_price_online(message: Message, state: FSMContext):
    """Обработка надбавки за онлайн"""
    if not await check_admin_access(message):
        await state.clear()
        return
    
    try:
        surcharge = float(message.text.strip().replace(',', '.'))
        if surcharge < 0:
            raise ValueError
        
        await state.update_data(online_surcharge=surcharge)
        await state.set_state(AdminPanelStates.setting_price_grade_9)
        await message.answer(
            f"✅ Надбавка за онлайн: <b>+{int(surcharge)}₽</b>\n\n"
            f"💰 Введите надбавку за 9 класс:\n\n"
            f"Например: <b>300</b>",
            parse_mode="HTML",
            reply_markup=kb.back_to_admin_button()
        )
    except ValueError:
        await message.answer("❌ Введите корректную надбавку (неотрицательное число)")

@router.message(AdminPanelStates.setting_price_grade_9)
async def process_price_grade_9(message: Message, state: FSMContext):
    """Обработка надбавки за 9 класс"""
    if not await check_admin_access(message):
        await state.clear()
        return
    
    try:
        surcharge = float(message.text.strip().replace(',', '.'))
        if surcharge < 0:
            raise ValueError
        
        await state.update_data(grade_9_surcharge=surcharge)
        await state.set_state(AdminPanelStates.setting_price_grade_10_11)
        await message.answer(
            f"✅ Надбавка за 9 класс: <b>+{int(surcharge)}₽</b>\n\n"
            f"💰 Введите надбавку за 10-11 класс:\n\n"
            f"Например: <b>500</b>",
            parse_mode="HTML",
            reply_markup=kb.back_to_admin_button()
        )
    except ValueError:
        await message.answer("❌ Введите корректную надбавку (неотрицательное число)")

@router.message(AdminPanelStates.setting_price_grade_10_11)
async def process_price_grade_10_11(message: Message, state: FSMContext):
    """Обработка надбавки за 10-11 класс"""
    if not await check_admin_access(message):
        await state.clear()
        return
    
    try:
        surcharge = float(message.text.strip().replace(',', '.'))
        if surcharge < 0:
            raise ValueError
        
        await state.update_data(grade_10_11_surcharge=surcharge)
        await state.set_state(AdminPanelStates.setting_price_profile)
        await message.answer(
            f"✅ Надбавка за 10-11 класс: <b>+{int(surcharge)}₽</b>\n\n"
            f"💰 Введите надбавку за профильное направление:\n\n"
            f"Например: <b>200</b>",
            parse_mode="HTML",
            reply_markup=kb.back_to_admin_button()
        )
    except ValueError:
        await message.answer("❌ Введите корректную надбавку (неотрицательное число)")

@router.message(AdminPanelStates.setting_price_profile)
async def process_price_profile(message: Message, state: FSMContext):
    """Обработка надбавки за профиль и сохранение всех настроек"""
    if not await check_admin_access(message):
        await state.clear()
        return
    
    try:
        surcharge = float(message.text.strip().replace(',', '.'))
        if surcharge < 0:
            raise ValueError
        
        data = await state.get_data()
        
        # Сохраняем все настройки
        success = await db.save_price_settings(
            base_price=data['base_price'],
            online_surcharge=data['online_surcharge'],
            grade_9_surcharge=data['grade_9_surcharge'],
            grade_10_11_surcharge=data['grade_10_11_surcharge'],
            profile_surcharge=surcharge
        )
        
        if success:
            # Получаем обновленные настройки для отображения таблицы
            settings = await db.get_price_settings()
            combinations = db.get_all_price_combinations(settings)
            
            text = "✅ <b>Настройки цен сохранены!</b>\n\n"
            text += "<b>Текущие параметры:</b>\n"
            text += f"• Базовая цена: {int(settings['base_price'])}₽/час\n"
            text += f"• Надбавка за онлайн: +{int(settings['online_surcharge'])}₽\n"
            text += f"• Надбавка за 9 класс: +{int(settings['grade_9_surcharge'])}₽\n"
            text += f"• Надбавка за 10-11 класс: +{int(settings['grade_10_11_surcharge'])}₽\n"
            text += f"• Надбавка за профиль: +{int(settings['profile_surcharge'])}₽\n\n"
            text += "<b>📊 Таблица цен:</b>\n"
            
            for combo in combinations:
                text += f"• {combo['grade_range']}, {combo['subject']}, {combo['format']}: {int(combo['price'])}₽/час\n"
            
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=kb.price_settings_keyboard(has_settings=True)
            )
        else:
            await message.answer("❌ Ошибка при сохранении настроек", reply_markup=kb.back_to_admin_button())
        
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите корректную надбавку (неотрицательное число)")

# Обработчики редактирования отдельных параметров
@router.callback_query(F.data.startswith("edit_price_"))
async def edit_price_setting(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование параметра цены"""
    if not await check_admin_access_callback(callback):
        return
    
    setting_name = callback.data.replace("edit_price_", "")
    setting_map = {
        'base': ('base_price', 'базовую цену', 'Базовая цена за час (для 5-8 класс, база, очно):'),
        'online': ('online_surcharge', 'надбавку за онлайн', 'Надбавка за онлайн формат:'),
        'grade_9': ('grade_9_surcharge', 'надбавку за 9 класс', 'Надбавка за 9 класс:'),
        'grade_10_11': ('grade_10_11_surcharge', 'надбавку за 10-11 класс', 'Надбавка за 10-11 класс:'),
        'profile': ('profile_surcharge', 'надбавку за профиль', 'Надбавка за профильное направление:')
    }
    
    if setting_name not in setting_map:
        await callback.answer("❌ Неизвестный параметр", show_alert=True)
        return
    
    db_name, display_name, prompt = setting_map[setting_name]
    await state.set_state(AdminPanelStates.editing_price_setting)
    await state.update_data(setting_name=db_name)
    
    await callback.message.edit_text(
        f"✏️ <b>Изменение {display_name}</b>\n\n"
        f"💰 {prompt}",
        parse_mode="HTML",
        reply_markup=kb.back_to_admin_button()
    )
    await callback.answer()

@router.message(AdminPanelStates.editing_price_setting)
async def process_edit_price_setting(message: Message, state: FSMContext):
    """Обработка изменения параметра цены"""
    if not await check_admin_access(message):
        await state.clear()
        return
    
    try:
        price = float(message.text.strip().replace(',', '.'))
        data = await state.get_data()
        setting_name = data.get('setting_name')
        
        if not setting_name:
            await message.answer("❌ Ошибка: параметр не найден")
            await state.clear()
            return
        
        # Проверка валидации
        if setting_name == 'base_price' and price <= 0:
            await message.answer("❌ Базовая цена должна быть положительным числом")
            return
        
        if price < 0:
            await message.answer("❌ Надбавка не может быть отрицательной")
            return
        
        # Обновляем параметр
        success = await db.update_price_setting(setting_name, price)
        
        if success:
            # Получаем обновленные настройки
            settings = await db.get_price_settings()
            combinations = db.get_all_price_combinations(settings)
            
            text = "✅ <b>Параметр обновлен!</b>\n\n"
            text += "<b>Текущие параметры:</b>\n"
            text += f"• Базовая цена: {int(settings['base_price'])}₽/час\n"
            text += f"• Надбавка за онлайн: +{int(settings['online_surcharge'])}₽\n"
            text += f"• Надбавка за 9 класс: +{int(settings['grade_9_surcharge'])}₽\n"
            text += f"• Надбавка за 10-11 класс: +{int(settings['grade_10_11_surcharge'])}₽\n"
            text += f"• Надбавка за профиль: +{int(settings['profile_surcharge'])}₽\n\n"
            text += "<b>📊 Таблица цен:</b>\n"
            
            for combo in combinations:
                text += f"• {combo['grade_range']}, {combo['subject']}, {combo['format']}: {int(combo['price'])}₽/час\n"
            
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=kb.price_settings_keyboard(has_settings=True)
            )
        else:
            await message.answer("❌ Ошибка при обновлении параметра", reply_markup=kb.back_to_admin_button())
        
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите корректное число")

#Поиск студента
@router.callback_query(F.data == "search_student")
async def search_student_start(callback: CallbackQuery, state: FSMContext):
    # Проверка прав
    if not await check_admin_access_callback(callback):
        return
    
    await callback.message.edit_text(
        "🔍 ПОИСК УЧЕНИКА\n\n"
        "Введите имя ученика или @username:\n\n"
        "Примеры:\n"
        "• Иванов Иван\n"
        "• @ivan_student\n\n"
    )
    
    await state.set_state(AdminPanelStates.searching_student)
    await callback.answer()

@router.message(AdminPanelStates.searching_student)
async def search_student_process(message: Message, state: FSMContext):
    # Проверка прав
    if not await check_admin_access(message):
        return
    
    query = message.text.strip()
    
    # Определяем тип поиска
    if query.startswith('@'):
        # Поиск по username
        student = await db.search_student_by_username(query)
        
        if student:
            # Нашли одного ученика
            username_text = f"{student['username']}" if student['username'] else "нет username"
            
            await message.answer(
                f"✅ Найден ученик:\n\n"
                f"👤 {student['name']}\n"
                f"📱 Username: {username_text}\n"
                f"🎓 Класс: {student['grade']}\n"
                f"📊 Направление: {student['subject']}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="📖 Открыть профиль",
                        callback_data=f"view_student_{student['user_id']}"
                    )],
                    [InlineKeyboardButton(text="🔙 К списку", callback_data="show_students_list")]
                ])
            )
        else:
            await message.answer(
                f"❌ Ученик с username {query} не найден.\n\n"
                f"Попробуйте найти по имени.",
                reply_markup=kb.back_to_students
            )
    else:
        # Поиск по имени
        students = await db.search_student_by_name(query)
        
        if students:
            if len(students) == 1:
                # Нашли одного
                student = students[0]
                username_text = f"{student['username']}" if student['username'] else "нет username"
                
                await message.answer(
                    f"✅ Найден ученик:\n\n"
                    f"👤 {student['name']}\n"
                    f"📱 Username: {username_text}\n"
                    f"🎓 Класс: {student['grade']}\n"
                    f"📊 Направление: {student['subject']}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="📖 Открыть профиль",
                            callback_data=f"view_student_{student['user_id']}"
                        )],
                        [InlineKeyboardButton(text="🔙 К списку", callback_data="show_students_list")]
                    ])
                )
            else:
                # Нашли несколько
                keyboard = kb.generate_students_list(students)
                
                await message.answer(
                    f"🔍 Найдено учеников: {len(students)}\n\n"
                    f"Выберите нужного:",
                    reply_markup=keyboard
                )
        else:
            await message.answer(
                f"❌ Ученики с именем {query} не найдены.\n\n"
                f"Попробуйте изменить запрос.",
                reply_markup=kb.back_to_students
            )
    
    await state.clear()

@router.callback_query(F.data.startswith("student_stats_"))
async def show_student_statistics(callback: CallbackQuery):
    """Показать детальную статистику ученика"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        student_id = int(callback.data.split("_")[2])
        
        # Получаем данные ученика
        student = await db.get_student(student_id)
        if not student:
            await callback.answer("❌ Ученик не найден", show_alert=True)
            return
        
        # Получаем статистику
        stats = await db.get_student_lessons_stats(student_id)
        if not stats:
            await callback.answer("❌ Не удалось получить статистику", show_alert=True)
            return
        
        # Получаем все занятия для расчета дополнительных метрик
        all_lessons = await db.get_lessons_by_student(student_id)
        completed_lessons = [l for l in all_lessons if l.get('status') == 'completed']
        cancelled_lessons = [l for l in all_lessons if l.get('status') == 'cancelled']
        
        # Считаем среднюю стоимость (только для оплаченных занятий за год)
        year_count = stats.get('year', {}).get('count', 0)
        year_sum = stats.get('year', {}).get('sum', 0) or 0
        avg_price = int(year_sum / year_count) if year_count > 0 else 0
        
        # Считаем посещаемость (проведенные / (проведенные + отмененные) * 100)
        total_planned = len(completed_lessons) + len(cancelled_lessons)
        attendance = int((len(completed_lessons) / total_planned * 100)) if total_planned > 0 else 0
        
        # Получаем задолженность
        debt_info = await db.get_student_debt(student_id)
        if not debt_info:
            debt_info = {'total_debt': 0, 'unpaid_count': 0}
        
        # Считаем общую сумму всех завершенных занятий (оплаченных и неоплаченных)
        total_completed_sum = sum((float(l.get('price') or 0)) for l in completed_lessons)
        
        # Формируем текст статистики (компактно для мобильных)
        stats_text = f"""📊 <b>Статистика: {student['name']}</b>

📅 <b>Занятия (оплаченные):</b>
Месяц: {stats.get('month', {}).get('count', 0)} ({int(stats.get('month', {}).get('sum', 0) or 0)}₽)
Полгода: {stats.get('half_year', {}).get('count', 0)} ({int(stats.get('half_year', {}).get('sum', 0) or 0)}₽)
Год: {year_count} ({int(year_sum)}₽)

💰 <b>Финансы:</b>
Проведено: {int(total_completed_sum)}₽
Оплачено: <b>{int(year_sum)}₽</b>
Долг: <b>{int(debt_info.get('total_debt', 0) or 0)}₽</b>

📈 <b>Показатели:</b>
Средняя стоимость: {avg_price}₽
Посещаемость: {attendance}%
Отменено: {len(cancelled_lessons)}"""
        
        # Клавиатура возврата
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ К профилю ученика", callback_data=f"view_student_{student_id}")]
        ])
        
        await callback.message.edit_text(
            stats_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в show_student_statistics: {error_details}")
        await callback.answer(f"❌ Ошибка при загрузке статистики: {str(e)}", show_alert=True)
        try:
            # Пытаемся вернуться к профилю ученика
            student_id = int(callback.data.split("_")[2])
            await callback.message.edit_text(
                "❌ Произошла ошибка при загрузке статистики",
                reply_markup=kb.generate_student_card_keyboard(student_id)
            )
        except:
            await callback.message.edit_text(
                "❌ Произошла ошибка при загрузке статистики",
                reply_markup=kb.back_to_admin_button()
            )

@router.callback_query(F.data.startswith("view_homework_"))
async def show_student_homework(callback: CallbackQuery):
    """Показать домашние задания ученика (для учителя)"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        # Определяем, показывать ли все ДЗ или только активные
        show_all = callback.data.startswith("view_homework_all_")
        
        if show_all:
            student_id = int(callback.data.split("_")[3])
        else:
            student_id = int(callback.data.split("_")[2])
        
        # Получаем данные ученика
        student = await db.get_student(student_id)
        if not student:
            await callback.answer("❌ Ученик не найден", show_alert=True)
            return
        
        # Получаем ДЗ с умным фильтром (прошлая и следующая неделя)
        homework_data = await db.get_student_homework_smart(student_id)
        past_week = homework_data.get('active', [])  # Прошлая неделя
        next_week = homework_data.get('recent', [])    # Следующая неделя
        
        # Объединяем занятия прошлой и следующей недели
        all_homework_lessons = past_week + next_week
        
        # Формируем текст сообщения
        message_text = f"📖 <b>Домашние задания: {student['name']}</b>\n\n"
        
        if not all_homework_lessons:
            message_text += "📭 Нет домашних заданий за прошлую и следующую неделю"
        else:
            # Прошлая неделя
            if past_week:
                message_text += "📅 <b>Прошлая неделя:</b>\n"
                for lesson in past_week:
                    date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)
                    homework_text = (lesson.get('homework') or '').strip()
                    # Обрезаем длинное ДЗ для мобильных
                    if len(homework_text) > 80:
                        homework_text = homework_text[:77] + "..."
                    message_text += f"• {date_str}\n📝 {homework_text}\n\n"
                message_text += "\n"
            
            # Следующая неделя
            if next_week:
                message_text += "🔮 <b>Следующая неделя:</b>\n"
                for lesson in next_week:
                    date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)
                    homework_text = (lesson.get('homework') or '').strip()
                    # Обрезаем длинное ДЗ для мобильных
                    if len(homework_text) > 80:
                        homework_text = homework_text[:77] + "..."
                    message_text += f"• {date_str}\n📝 {homework_text}\n\n"
        
        # Клавиатура со списком ДЗ для редактирования
        keyboard = kb.homework_list_keyboard(all_homework_lessons, student_id, show_all=False)
        
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в show_student_homework: {error_details}")
        await callback.answer(f"❌ Ошибка при загрузке ДЗ: {str(e)}", show_alert=True)
        try:
            student_id = int(callback.data.split("_")[-1])
            await callback.message.edit_text(
                "❌ Произошла ошибка при загрузке ДЗ",
                reply_markup=kb.generate_student_card_keyboard(student_id)
            )
        except:
            await callback.message.edit_text(
                "❌ Произошла ошибка при загрузке ДЗ",
                reply_markup=kb.back_to_admin_button()
            )

@router.callback_query(F.data.startswith("edit_homework_"))
async def handle_edit_homework(callback: CallbackQuery, state: FSMContext):
    """Начать процесс редактирования/добавления домашнего задания"""
    if not await check_admin_access_callback(callback):
        return
    
    # Извлекаем lesson_id и student_id из callback_data: "edit_homework_{lesson_id}_{student_id}"
    parts = callback.data.split("_")
    lesson_id = int(parts[2])
    student_id = int(parts[3])
    
    # Получаем занятие для показа текущего ДЗ (если есть)
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.answer("❌ Занятие не найдено", show_alert=True)
        return
    
    # Сохраняем lesson_id и student_id в состояние + флаг, что вызвано из списка ДЗ
    await state.update_data(
        lesson_id=lesson_id,
        student_id=student_id,
        from_homework_list=True  # Добавляем флаг, что это из списка ДЗ
    )
    await state.set_state(AdminPanelStates.editing_homework)
    
    # Формируем сообщение с текущим ДЗ (если есть)
    current_homework = (lesson.get('homework') or '').strip()
    if current_homework:
        message_text = f"✏️ <b>Текущее ДЗ:</b>\n{current_homework}\n\n📝 Введите новое ДЗ (или оставьте текущее):"
    else:
        message_text = "📝 Введите текст домашнего задания:"
    
    await callback.message.edit_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"view_homework_{student_id}")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(AdminPanelStates.editing_homework)
async def process_edit_homework(message: Message, state: FSMContext, bot: Bot):
    """Обработать текст при редактировании домашнего задания и спросить про фото"""
    data = await state.get_data()
    lesson_id = data.get('lesson_id')
    student_id = data.get('student_id')
    homework_text = message.text
    
    # Получаем информацию о занятии для проверки текущего фото
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await message.answer("❌ Занятие не найдено")
        await state.clear()
        return
    
    # Сохраняем текст ДЗ во временное хранилище
    await state.update_data(homework_text=homework_text)
    
    # Проверяем, есть ли уже вложения у ДЗ (вариант C - отдельные опции)
    current_photo = lesson.get('homework_photo_file_id')
    current_file = lesson.get('homework_file_id')
    has_photo = bool(current_photo)
    has_file = bool(current_file)
    
    # Формируем клавиатуру с отдельными опциями для фото и файла
    buttons = []
    
    # Опции для фото
    if has_photo:
        buttons.append([
            InlineKeyboardButton(text="📷 Оставить фото", callback_data="homework_keep_photo"),
            InlineKeyboardButton(text="📷 Заменить фото", callback_data="homework_replace_photo")
        ])
        buttons.append([InlineKeyboardButton(text="📷 Удалить фото", callback_data="homework_remove_photo")])
    else:
        buttons.append([InlineKeyboardButton(text="📷 Добавить фото", callback_data="homework_add_photo")])
    
    # Опции для файла
    if has_file:
        buttons.append([
            InlineKeyboardButton(text="📎 Оставить файл", callback_data="homework_keep_file"),
            InlineKeyboardButton(text="📎 Заменить файл", callback_data="homework_replace_file")
        ])
        buttons.append([InlineKeyboardButton(text="📎 Удалить файл", callback_data="homework_remove_file")])
    else:
        buttons.append([InlineKeyboardButton(text="📎 Добавить файл", callback_data="homework_add_file")])
    
    # Кнопка сохранения без изменений вложений
    buttons.append([InlineKeyboardButton(text="✅ Сохранить без изменений вложений", callback_data="homework_save_no_changes")])
    
    await state.set_state(AdminPanelStates.adding_homework_photo)
    
    attachment_info = []
    if has_photo:
        attachment_info.append("📷 фото")
    if has_file:
        attachment_info.append("📎 файл")
    attachment_text = f"У этого ДЗ уже есть: {', '.join(attachment_info)}" if attachment_info else "У этого ДЗ нет вложений"
    
    await message.answer(
        f"📝 Текст ДЗ сохранен:\n\n{homework_text}\n\n"
        f"{attachment_text}\n\n"
        f"Что хотите сделать с вложениями?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data.startswith("new_student_"))
async def show_new_student_card(callback: CallbackQuery, state: FSMContext):
    """Показать информацию о регистрации нового ученика"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        student_id = int(callback.data.split("_")[2])
        
        # Получаем данные ученика
        student = await db.get_student(student_id)
        if not student:
            await callback.answer("❌ Ученик не найден", show_alert=True)
            return
        
        # Помечаем ученика как просмотренного
        await db.mark_student_viewed(student_id)
        
        # Формируем информацию о регистрации
        telegram_full_name = student.get('telegram_full_name', 'не указано')
        username = student.get('username', 'не указан')
        if username and not username.startswith('@'):
            username = f"@{username}"
        
        registration_format = student.get('registration_format', 'не указано')
        format_text = 'онлайн' if registration_format == 'online' else 'оффлайн' if registration_format == 'offline' else registration_format
        
        registration_price = student.get('registration_price')
        price_text = f"{int(registration_price)} руб." if registration_price else "не указана"
        
        registration_feedback = student.get('registration_feedback', 'не указано')
        
        subject_text = 'профиль' if 'профиль' in student.get('subject', '').lower() else 'база'
        
        registration_info = (
            f"📋 <b>Новая регистрация:</b>\n\n"
            f"👤 <b>Пользователь:</b> {telegram_full_name}\n"
            f"🔗 <b>username:</b> {username}\n"
            f"🆔 <b>ID:</b> {student_id}\n"
            f"📚 <b>Класс:</b> {student['grade']}\n"
            f"🎯 <b>Направление:</b> {subject_text}\n"
            f"💻 <b>Формат:</b> {format_text}\n"
            f"💰 <b>Стоимость:</b> {price_text}\n"
            f"👨‍🎓 <b>ФИО:</b> {student['name']}\n"
            f"📞 <b>Телефон:</b> {student['phone']}\n"
            f"📢 <b>Откуда узнали:</b> {registration_feedback}"
        )
        
        # Клавиатура с кнопкой открытия профиля
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Открыть профиль", callback_data=f"view_student_{student_id}")],
            [InlineKeyboardButton(text="🔙 К списку новых", callback_data="show_new_students")]
        ])
        
        await callback.message.edit_text(
            registration_info,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в show_new_student_card: {error_details}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.callback_query(F.data.startswith("view_student_"))
async def show_student_card(callback: CallbackQuery, state: FSMContext):
    """Показать карточку ученика (обычный просмотр)"""
    student_id = int(callback.data.split("_")[2])
    await show_student_card_internal(callback, student_id, state)

async def show_student_card_internal(callback: CallbackQuery, student_id: int, state: FSMContext):
    """Внутренняя функция для отображения карточки ученика"""
    # Проверка прав
    if not await check_admin_access_callback(callback):
        return
    
    try:
        # Получаем данные ученика
        student = await db.get_student(student_id)
        
        if not student:
            await callback.answer("❌ Ученик не найден", show_alert=True)
            return
        
        # Получаем расписание ученика
        schedules = await db.get_student_schedules(student_id)
        
        # Получаем задолженность
        debt_info = await db.get_student_debt(student_id)
        
        # Форматируем username (добавляем @ если нет)
        username = student['username'] if student['username'] else None
        if username and not username.startswith('@'):
            username_display = f"@{username}"
        elif username:
            username_display = username
        else:
            username_display = ""
        
        # Формируем имя с username
        if username_display:
            name_line = f"🎓 {student['name']}({username_display})"
        else:
            name_line = f"🎓 {student['name']}"
        
        # Форматируем класс и направление
        class_info = f"Класс {student['grade']}"
        if student['subject']:
            class_info += f" • {student['subject']}"
        
        # Форматируем расписание (компактно для мобильных)
        if schedules:
            schedule_lines = []
            for s in schedules:
                weekday_short = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 
                               4: "Пт", 5: "Сб", 6: "Вс"}
                weekday = weekday_short.get(s['weekday'], "")
                format_emoji = "💻" if s['lesson_format'] == 'online' else "🏠"
                duration = s.get('duration', 60)
                duration_text = f"{duration//60}ч" if duration >= 60 else f"{duration}м"
                schedule_lines.append(
                    f"• {weekday} {s['time']} ({format_emoji} {duration_text}, {int(s['price'])}₽)"
                )
            schedule_text = "\n".join(schedule_lines)
        else:
            schedule_text = "Расписание не настроено"
        
        # Форматируем задолженность
        debt_text = f"💰 Долг: {int(debt_info['total_debt'])}₽"

        # Формируем текст карточки согласно новому формату
        card_text = f"""{name_line}
{class_info}
📞 Телефон: {student['phone']}
📆 Расписание:
{schedule_text}

{debt_text}"""
        
        # Проверяем, является ли исходное сообщение уведомлением об окончании занятия
        # Если да - отправляем новое сообщение, чтобы не затереть уведомление
        original_text = callback.message.text or ""
        is_lesson_ending_notification = (
            "⏰" in original_text and 
            ("Занятие завершается" in original_text or "Окончание:" in original_text)
        )
        
        if is_lesson_ending_notification:
            # Отправляем новое сообщение, исходное остается нетронутым
            await callback.message.answer(
                card_text,
                reply_markup=kb.generate_student_card_keyboard(student_id),
                parse_mode="HTML"
            )
        else:
            # Редактируем исходное сообщение как обычно
            await callback.message.edit_text(
                card_text,
                reply_markup=kb.generate_student_card_keyboard(student_id),
                parse_mode="HTML"
            )
        await callback.answer()
        
    except Exception as e:
        await callback.message.edit_text(
            "❌ Произошла ошибка при загрузке данных ученика",
            reply_markup=kb.back_to_admin_button()
        )
        await callback.answer()
        
        # # Генерируем клавиатуру
        # keyboard = kb.generate_student_card_keyboard(student_id)
        
        # await callback.message.edit_text(
        #     card_text,
        #     reply_markup=keyboard
        # )
        # await callback.answer()

@router.callback_query(F.data == "show_students_list")
async def show_students_callback(callback: CallbackQuery, state: FSMContext):
    # Проверка прав
    if not await check_admin_access_callback(callback):
        return
    
    await state.clear()
    
    students = await db.get_all_students()
    total_count = len(students)
    
    keyboard = kb.generate_students_list(students)
    
    await callback.message.edit_text(
        f"      📚 СПИСОК УЧЕНИКОВ ({total_count})\n\n"
        f"Выберите ученика для просмотра профиля:",
        reply_markup=keyboard
    )
    await safe_callback_answer(callback)

@router.callback_query(F.data.startswith("edit_schedule_item_"))
async def show_schedule_item_actions(callback: CallbackQuery, state: FSMContext):
    """Показать действия для конкретного элемента расписания"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        schedule_id = int(callback.data.split("_")[3])
        
        # Получаем данные расписания
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT s.*, st.name as student_name, st.user_id as student_id
                   FROM schedules s 
                   JOIN students st ON s.student_id = st.user_id 
                   WHERE s.id = ?""", 
                (schedule_id,)
            )
            schedule = await cursor.fetchone()
        
        if not schedule:
            await callback.answer("❌ Расписание не найдено", show_alert=True)
            return
        
        schedule = dict(schedule)
        weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        format_text = "🏠 Очно" if schedule['lesson_format'] == "offline" else "💻 Онлайн"
        
        schedule_text = f"""📅 <b>Управление расписанием</b>

👤 <b>Ученик:</b> {schedule['student_name']}
📅 <b>День:</b> {weekday_names[schedule['weekday']]}
🕐 <b>Время:</b> {schedule['time']}
🏠 <b>Формат:</b> {format_text}
💰 <b>Стоимость:</b> {int(schedule['price'])}₽

Что хотите сделать?"""
        
        await callback.message.edit_text(
            schedule_text,
            reply_markup=kb.schedule_item_actions_keyboard(schedule_id, schedule['student_id']),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer("❌ Ошибка загрузки", show_alert=True)

@router.callback_query(F.data.startswith("delete_schedule_"))
async def confirm_delete_schedule(callback: CallbackQuery):
    """Подтверждение удаления расписания"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        schedule_id = int(callback.data.split("_")[2])
        
        # Получаем данные для подтверждения
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT s.*, st.name as student_name, st.user_id as student_id
                   FROM schedules s 
                   JOIN students st ON s.student_id = st.user_id 
                   WHERE s.id = ?""", 
                (schedule_id,)
            )
            schedule = await cursor.fetchone()
        
        if not schedule:
            await callback.answer("❌ Расписание не найдено", show_alert=True)
            return
        
        schedule = dict(schedule)
        weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        
        confirm_text = f"""❌ <b>Удаление расписания</b>

👤 <b>Ученик:</b> {schedule['student_name']}
📅 <b>Расписание:</b> {weekday_names[schedule['weekday']]} в {schedule['time']}

⚠️ <b>Внимание!</b> При удалении расписания будущие занятия, созданные по этому шаблону, останутся без изменений.

Точно удалить?"""
        
        await callback.message.edit_text(
            confirm_text,
            reply_markup=kb.schedule_delete_confirmation_keyboard(schedule_id, schedule['student_id']),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("confirm_delete_schedule_"))
async def delete_schedule_confirmed(callback: CallbackQuery, bot: Bot):
    if not await check_admin_access_callback(callback):
        return
    
    try:
        schedule_id = int(callback.data.split("_")[3])
        
        # Получаем информацию о расписании перед удалением
        schedule_info = None
        cancelled_count = 0
        
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            # Получаем информацию о расписании
            cursor = await db.execute("""
                SELECT s.*, st.name as student_name, st.user_id as student_id
                FROM schedules s 
                JOIN students st ON s.student_id = st.user_id 
                WHERE s.id = ?
            """, (schedule_id,))
            result = await cursor.fetchone()
            if not result:
                await callback.answer("❌ Расписание не найдено", show_alert=True)
                return
            schedule_info = dict(result)
            student_id = schedule_info['student_id']
            
            # Считаем количество будущих занятий, которые будут отменены
            cursor = await db.execute("""
                SELECT COUNT(*) as count
                FROM lessons 
                WHERE schedule_id = ? 
                AND status = 'scheduled'
                AND lesson_date >= date('now')
            """, (schedule_id,))
            cancelled_count_result = await cursor.fetchone()
            cancelled_count = cancelled_count_result['count'] if cancelled_count_result else 0
            
            # Отменяем все будущие занятия, связанные с этим расписанием
            await db.execute("""
                UPDATE lessons 
                SET status = 'cancelled' 
                WHERE schedule_id = ? 
                AND status = 'scheduled'
                AND lesson_date >= date('now')
            """, (schedule_id,))
            
            # Удаляем расписание
            await db.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
            await db.commit()
        
        # Отправляем уведомление ученику
        weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        format_text = "онлайн" if schedule_info['lesson_format'] == 'online' else "оффлайн"
        
        notification_text = (
            f"❌ <b>Расписание удалено</b>\n\n"
            f"📅 День недели: {weekday_names[schedule_info['weekday']]}\n"
            f"🕐 Время: {schedule_info['time']}\n"
            f"📍 Формат: {format_text}\n"
        )
        
        if cancelled_count > 0:
            notification_text += f"\n⚠️ Отменено будущих занятий: {cancelled_count}"
        
        try:
            await bot.send_message(
                chat_id=student_id,
                text=notification_text,
                parse_mode="HTML"
            )
            logger.info(f" Отправлено уведомление ученику {schedule_info['student_name']} об удалении расписания")
        except Exception as e:
            logger.warning(f" Не удалось отправить уведомление ученику {student_id}: {e}")
        
        await callback.message.edit_text(
            "✅ <b>Расписание удалено!</b>\n\n"
            f"Связанные будущие занятия отменены ({cancelled_count}).",
            reply_markup=kb.back_to_student_profile(student_id),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        await callback.message.edit_text("❌ Ошибка при удалении расписания")
        await callback.answer()


@router.callback_query(F.data.startswith("modify_schedule_"))
async def show_modify_options(callback: CallbackQuery):
    """Показать опции изменения расписания"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        schedule_id = int(callback.data.split("_")[2])
        
        await callback.message.edit_text(
            "✏️ <b>Редактирование расписания</b>\n\n"
            "Что хотите изменить?",
            reply_markup=kb.schedule_modify_options_keyboard(schedule_id),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("modify_day_"))
async def modify_schedule_day(callback: CallbackQuery):
    """Начать изменение дня недели"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        schedule_id = int(callback.data.split("_")[2])
        
        await callback.message.edit_text(
            "📅 <b>Изменение дня недели</b>\n\n"
            "Выберите новый день:",
            reply_markup=kb.weekday_selection_for_edit_keyboard(schedule_id),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("edit_weekday_"))
async def update_schedule_weekday(callback: CallbackQuery, bot: Bot):
    """Обновить день недели расписания"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        parts = callback.data.split("_")
        weekday = int(parts[2])
        schedule_id = int(parts[3])
        
        # Получаем старое расписание
        old_schedule = await db.get_schedule(schedule_id)
        if not old_schedule:
            await callback.answer("❌ Расписание не найдено", show_alert=True)
            return
        
        # Обновляем в БД
        success = await db.update_schedule_weekday(schedule_id, weekday)
        
        if success:
            # Пересоздаем будущие занятия
            await db.recreate_future_lessons_from_schedule(schedule_id)
            
            # Получаем новое расписание
            new_schedule = await db.get_schedule(schedule_id)
            
            # Отправляем уведомление ученику
            if new_schedule:
                await send_schedule_change_notification(bot, old_schedule['student_id'], old_schedule, new_schedule)
            
            weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
            await callback.message.edit_text(
                f"✅ <b>День недели изменен!</b>\n\n"
                f"Новый день: <b>{weekday_names[weekday]}</b>\n\n"
                f"Будущие занятия обновлены автоматически.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ К расписанию", callback_data=f"edit_schedule_item_{schedule_id}")]
                ]),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                "❌ Ошибка при изменении дня недели",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data=f"edit_schedule_item_{schedule_id}")]
                ])
            )
        
        await callback.answer()
        
    except Exception as e:
        import traceback
        logger.error(f"Ошибка в update_schedule_weekday: {traceback.format_exc()}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("modify_time_"))
async def modify_schedule_time(callback: CallbackQuery, state: FSMContext):
    """Начать изменение времени"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        schedule_id = int(callback.data.split("_")[2])
        
        await state.set_state(AdminPanelStates.editing_schedule_time)
        await state.update_data(editing_schedule_id=schedule_id)
        
        await callback.message.edit_text(
            "🕐 <b>Изменение времени</b>\n\n"
            "Введите новое время в формате ЧЧ:ММ (например: 17:30):",
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.message(AdminPanelStates.editing_schedule_time)
async def update_schedule_time(message: Message, state: FSMContext, bot: Bot):
    """Обновить время расписания"""
    if not await check_admin_access(message):
        return
    
    time_text = message.text.strip()
    
    # Проверяем формат времени
    try:
        datetime.strptime(time_text, '%H:%M')
    except ValueError:
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ:ММ (например: 17:30)")
        return
    
    try:
        data = await state.get_data()
        schedule_id = data['editing_schedule_id']
        
        # Получаем старое расписание
        old_schedule = await db.get_schedule(schedule_id)
        if not old_schedule:
            await message.answer("❌ Расписание не найдено")
            await state.clear()
            return
        
        # Обновляем в БД
        success = await db.update_schedule_time(schedule_id, time_text)
        
        if success:
            # Пересоздаем будущие занятия
            await db.recreate_future_lessons_from_schedule(schedule_id)
            
            # Получаем новое расписание
            new_schedule = await db.get_schedule(schedule_id)
            
            # Отправляем уведомление ученику
            if new_schedule:
                await send_schedule_change_notification(bot, old_schedule['student_id'], old_schedule, new_schedule)
            
            await message.answer(
                f"✅ <b>Время изменено!</b>\n\n"
                f"Новое время: <b>{time_text}</b>\n\n"
                f"Будущие занятия обновлены автоматически.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ К расписанию", callback_data=f"edit_schedule_item_{schedule_id}")]
                ]),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ Ошибка при изменении времени",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data=f"edit_schedule_item_{schedule_id}")]
                ])
            )
        
        await state.clear()
        
    except Exception as e:
        import traceback
        logger.error(f"Ошибка в update_schedule_time: {traceback.format_exc()}")
        await message.answer("❌ Произошла ошибка")
        await state.clear()

@router.callback_query(F.data.startswith("modify_format_"))
async def modify_schedule_format(callback: CallbackQuery):
    """Начать изменение формата занятия"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        schedule_id = int(callback.data.split("_")[2])
        
        await callback.message.edit_text(
            "🏠 <b>Изменение формата занятия</b>\n\n"
            "Выберите новый формат:",
            reply_markup=kb.lesson_format_edit_keyboard(schedule_id),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("edit_format_"))
async def update_schedule_format(callback: CallbackQuery, bot: Bot):
    """Обновить формат занятия"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        parts = callback.data.split("_")
        new_format = parts[2]  # "offline" или "online"
        schedule_id = int(parts[3])
        
        # Получаем старое расписание
        old_schedule = await db.get_schedule(schedule_id)
        if not old_schedule:
            await callback.answer("❌ Расписание не найдено", show_alert=True)
            return
        
        # Обновляем в БД
        success = await db.update_schedule_format(schedule_id, new_format)
        
        if success:
            # Пересоздаем будущие занятия
            await db.recreate_future_lessons_from_schedule(schedule_id)
            
            # Получаем новое расписание
            new_schedule = await db.get_schedule(schedule_id)
            
            # Отправляем уведомление ученику
            if new_schedule:
                await send_schedule_change_notification(bot, old_schedule['student_id'], old_schedule, new_schedule)
            
            format_text = "🏠 Очно" if new_format == "offline" else "💻 Онлайн"
            await callback.message.edit_text(
                f"✅ <b>Формат изменен!</b>\n\n"
                f"Новый формат: <b>{format_text}</b>\n\n"
                f"Будущие занятия обновлены автоматически.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ К расписанию", callback_data=f"edit_schedule_item_{schedule_id}")]
                ]),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                "❌ Ошибка при изменении формата",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data=f"edit_schedule_item_{schedule_id}")]
                ])
            )
        
        await callback.answer()
        
    except Exception as e:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("modify_price_"))
async def modify_schedule_price(callback: CallbackQuery, state: FSMContext):
    """Начать изменение стоимости"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        schedule_id = int(callback.data.split("_")[2])
        
        await state.set_state(AdminPanelStates.editing_schedule_price)
        await state.update_data(editing_schedule_id=schedule_id)
        
        await callback.message.edit_text(
            "💰 <b>Изменение стоимости</b>\n\n"
            "Введите новую стоимость в рублях (например: 1200):",
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.message(AdminPanelStates.editing_schedule_price)
async def update_schedule_price(message: Message, state: FSMContext, bot: Bot):
    """Обновить стоимость расписания"""
    if not await check_admin_access(message):
        return
    
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректную стоимость (положительное число)")
        return
    
    try:
        data = await state.get_data()
        schedule_id = data['editing_schedule_id']
        
        # Получаем старое расписание
        old_schedule = await db.get_schedule(schedule_id)
        if not old_schedule:
            await message.answer("❌ Расписание не найдено")
            await state.clear()
            return
        
        # Обновляем в БД
        success = await db.update_schedule_price(schedule_id, price)
        
        if success:
            # Пересоздаем будущие занятия
            await db.recreate_future_lessons_from_schedule(schedule_id)
            
            # Получаем новое расписание
            new_schedule = await db.get_schedule(schedule_id)
            
            # Отправляем уведомление ученику
            if new_schedule:
                await send_schedule_change_notification(bot, old_schedule['student_id'], old_schedule, new_schedule)
            
            await message.answer(
                f"✅ <b>Стоимость изменена!</b>\n\n"
                f"Новая стоимость: <b>{int(price)}₽</b>\n\n"
                f"Будущие занятия обновлены автоматически.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ К расписанию", callback_data=f"edit_schedule_item_{schedule_id}")]
                ]),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ Ошибка при изменении стоимости",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data=f"edit_schedule_item_{schedule_id}")]
                ])
            )
        
        await state.clear()
        
    except Exception as e:
        import traceback
        logger.error(f"Ошибка в update_schedule_price: {traceback.format_exc()}")
        await message.answer("❌ Произошла ошибка")
        await state.clear()


@router.callback_query(F.data.startswith("lessons_history_"))
async def show_lessons_history_teacher(callback: CallbackQuery):
    """История занятий для учителя с умным фильтром (по умолчанию)"""
    if not await check_admin_access_callback(callback):
        return

    try:
        student_id = int(callback.data.split("_")[2])
        
        # Используем умный фильтр по умолчанию
        await show_lessons_with_filter(callback, student_id, "smart")
        
    except Exception as e:
        logger.error(f"Ошибка в show_lessons_history_teacher: {e}")
        try:
            student_id = int(callback.data.split("_")[2])
            await callback.message.edit_text(
                "⚠️ Не удалось загрузить историю занятий.",
                reply_markup=kb.generate_student_card_keyboard(student_id)
            )
        except:
            await callback.message.edit_text(
                "⚠️ Не удалось загрузить историю занятий.",
                reply_markup=kb.back_to_admin_button()
            )
        await callback.answer()

async def show_lessons_with_filter(callback: CallbackQuery, student_id: int, filter_type: str = "smart"):
    """Показать занятия с выбранным фильтром"""
    student = await db.get_student(student_id)
    if not student:
        await callback.answer("❌ Ученик не найден", show_alert=True)
        return

    lessons_text = f"📚 <b>История занятий: {student['name']}</b>\n\n"
    
    if filter_type == "smart":
        # Умный фильтр: неделя назад + неделя вперед + неоплаченные
        lessons_data = await db.get_lessons_smart_filter(student_id)
        
        unpaid = lessons_data['unpaid']
        upcoming = lessons_data['upcoming']
        past = lessons_data['past']
        
        all_lessons = unpaid + upcoming + past
        
        if not all_lessons:
            lessons_text += (
                "📅 Нет занятий для отображения\n\n"
                "🎯 <b>Умный фильтр</b> показывает:\n"
                "• ⚠️ Неоплаченные занятия (все)\n"
                "• 🔮 Предстоящие на неделю\n"
                "• ✅ Прошедшие за неделю"
            )
            
            await callback.message.edit_text(
                lessons_text,
                reply_markup=kb.history_filter_keyboard(student_id, "smart"),
                parse_mode="HTML"
            )
            await safe_callback_answer(callback)
            return
        else:
            lessons_text += f"🎯 <b>Фильтр: Умный</b>\n\n"
            
            # Секция неоплаченных
            if unpaid:
                debt = sum(l['price'] for l in unpaid)
                lessons_text += f"⚠️ <b>Неоплаченные</b> (Долг: {debt:.0f}₽):\n"
                for l in unpaid[:5]:
                    date = format_date_with_weekday(l['lesson_date'], full_format=True)
                    time_str = format_lesson_time(l['lesson_time'], l.get('duration', 60))
                    lessons_text += f"❌ {date} {time_str} | {l['price']:.0f}₽\n"
                if len(unpaid) > 5:
                    lessons_text += f"... и еще {len(unpaid) - 5}\n"
                lessons_text += "\n"
            
            # Секция предстоящих
            if upcoming:
                lessons_text += f"🔮 <b>Предстоящие</b> (на неделю):\n"
                for l in upcoming[:5]:
                    date = format_date_with_weekday(l['lesson_date'])
                    time_str = format_lesson_time(l['lesson_time'], l.get('duration', 60))
                    lessons_text += f"⏳ {date} {time_str} | {l['price']:.0f}₽\n"
                if len(upcoming) > 5:
                    lessons_text += f"... и еще {len(upcoming) - 5}\n"
                lessons_text += "\n"
            
            # Секция прошедших
            if past:
                lessons_text += f"✅ <b>Прошедшие</b> (за неделю):\n"
                for l in past[:5]:
                    date = format_date_with_weekday(l['lesson_date'])
                    time_str = format_lesson_time(l['lesson_time'], l.get('duration', 60))
                    lessons_text += f"✅ {date} {time_str} | {l['price']:.0f}₽\n"
                if len(past) > 5:
                    lessons_text += f"... и еще {len(past) - 5}\n"

            await callback.message.edit_text(
            lessons_text,
            reply_markup=kb.lessons_with_filter_keyboard(student_id, all_lessons, "smart"),
            parse_mode="HTML"
        )
        
    elif filter_type == "unpaid":
        # Только неоплаченные
        lessons = await db.get_lessons_by_student(student_id)
        unpaid_lessons = [l for l in lessons if l['payment_status'] == 'unpaid' and l['status'] == 'completed']
        
        if not unpaid_lessons:
            lessons_text += "✅ Все занятия оплачены!"
            await callback.message.edit_text(
                lessons_text,
                reply_markup=kb.history_filter_keyboard(student_id, "unpaid"),
                parse_mode="HTML"
            )
            await safe_callback_answer(callback)
            return
        else:
            debt = sum(l['price'] for l in unpaid_lessons)
            lessons_text += f"❌ <b>Фильтр: Только неоплаченные</b>\n\n"
            lessons_text += f"💰 Всего долг: <b>{debt:.0f}₽</b>\n"
            lessons_text += f"📅 Занятий: {len(unpaid_lessons)}\n\n"
            
            for lesson in unpaid_lessons[:20]:
                date = format_date_with_weekday(lesson['lesson_date'], full_format=True)
                time_str = format_lesson_time(lesson['lesson_time'], lesson.get('duration', 60))
                lessons_text += f"❌ {date} {time_str} | {lesson['price']:.0f}₽\n"
        
        await callback.message.edit_text(
            lessons_text,
            reply_markup=kb.lessons_with_filter_keyboard(student_id, unpaid_lessons, "unpaid"),
            parse_mode="HTML"
        )
        
    elif filter_type == "all":
        # Все занятия
        lessons = await db.get_lessons_by_student(student_id)
        all_lessons = [l for l in lessons if l['status'] != 'cancelled']
        all_lessons.sort(key=lambda x: x['lesson_date'], reverse=True)
        
        if not all_lessons:
            lessons_text += "📅 У ученика нет занятий"
            await callback.message.edit_text(
                lessons_text,
                reply_markup=kb.history_filter_keyboard(student_id, "all"),
                parse_mode="HTML"
            )
            await safe_callback_answer(callback)
            return
        else:
            lessons_text += f"📅 <b>Фильтр: Все занятия</b>\n\n"
            lessons_text += f"Всего: {len(all_lessons)} занятий\n\n"
            
            for lesson in all_lessons[:20]:
                date = format_date_with_weekday(lesson['lesson_date'], full_format=True)
                status_emoji = "✅" if lesson['status'] == 'completed' else "⏳"
                pay_emoji = "✅" if lesson['payment_status'] == 'paid' else "❌"
                time_str = format_lesson_time(lesson['lesson_time'], lesson.get('duration', 60))
                lessons_text += f"{status_emoji} {date} {time_str} | {lesson['price']:.0f}₽ {pay_emoji}\n"
            
            if len(all_lessons) > 20:
                lessons_text += f"\n... и еще {len(all_lessons) - 20} занятий"
        
        await callback.message.edit_text(
            lessons_text,
            reply_markup=kb.lessons_with_filter_keyboard(student_id, all_lessons, "all"),
            parse_mode="HTML"
        )
        await callback.answer()

# Обработчики для расписания - ДОЛЖНЫ быть ПЕРЕД общим обработчиком schedule_
# чтобы не перехватывались более общим startswith("schedule_")

@router.callback_query(F.data == "schedule_today")
async def show_schedule_today_callback(callback: CallbackQuery):
    """Показать расписание на сегодня (callback версия)"""
    if not await check_admin_access_callback(callback):
            return

    try:
        today_lessons = await db.get_today_lessons()
        
        # Получаем текущую дату для заголовка
        today = get_local_time().date()
        weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        weekday_name = weekday_names[today.weekday()]
        date_str = today.strftime('%d.%m.%Y')
        
        message_text = f"📅 <b>РАСПИСАНИЕ НА СЕГОДНЯ</b>\n{date_str} ({weekday_name})\n\n"
        
        if not today_lessons:
            message_text += "✅ На сегодня занятий нет"
        else:
            for lesson in today_lessons:
                time_str = format_lesson_time(lesson['lesson_time'], lesson.get('duration', 60))
                
                # Мини-информация об ученике
                student_name = lesson['student_name']
                grade = lesson.get('grade', '')
                subject = lesson.get('subject', '')
                student_info = f"{student_name}"
                if grade:
                    student_info += f" ({grade}кл"
                    if subject:
                        student_info += f", {subject}"
                    student_info += ")"
                
                # ДЗ (обрезаем для мобильных)
                homework = (lesson.get('homework') or '').strip()
                if len(homework) > 50:
                    homework = homework[:47] + "..."
                
                # Цена
                price = int(lesson.get('price', 0))
                
                time_str = format_lesson_time(lesson['lesson_time'], lesson.get('duration', 60))
                message_text += f"🕐 <b>{time_str}</b>\n"
                message_text += f"👤 {student_info}\n"
                if homework:
                    message_text += f"📝 {homework}\n"
                message_text += f"💰 {price}₽\n\n"
        
        await callback.message.edit_text(
            message_text,
            reply_markup=kb.schedule_today_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в show_schedule_today_callback: {error_details}")
        await callback.answer("❌ Ошибка при загрузке расписания", show_alert=True)

@router.callback_query(F.data == "schedule_week_summary")
async def show_schedule_week_summary(callback: CallbackQuery):
    """Показать краткое расписание на неделю"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        week_summary = await db.get_week_lessons_summary()
        
        today = get_local_time().date()
        weekday_names_short = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        weekday_names_full = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        
        message_text = "📅 <b>КРАТКОЕ РАСПИСАНИЕ НА НЕДЕЛЮ</b>\n\n"
        
        if not week_summary:
            message_text += "✅ На эту неделю занятий нет"
        else:
            # Сортируем дни недели по порядку (начиная с сегодня)
            current_weekday = today.weekday()
            ordered_weekdays = []
            
            # Добавляем дни начиная с сегодня до конца недели
            for i in range(7):
                weekday_num = (current_weekday + i) % 7
                weekday_name = weekday_names_full[weekday_num]
                if weekday_name in week_summary:
                    ordered_weekdays.append(weekday_name)
            
            for weekday_name in ordered_weekdays:
                day_data = week_summary[weekday_name]
                day_short = weekday_names_short[weekday_names_full.index(weekday_name)]
                date_obj = day_data['date']
                date_str = date_obj.strftime('%d.%m')
                
                count = day_data['count']
                first_time = day_data['first_time']
                last_time = day_data['last_time']
                
                if first_time and last_time:
                    # Правильное склонение слова "занятие"
                    if count == 1:
                        lesson_word = "занятие"
                    elif count in [2, 3, 4]:
                        lesson_word = "занятия"
                    else:
                        lesson_word = "занятий"
                    
                    message_text += f"<b>{day_short} {date_str}</b>: {count} {lesson_word}"
                    if first_time != last_time:
                        message_text += f" ({first_time}-{last_time})"
                    else:
                        message_text += f" ({first_time})"
                    message_text += "\n"

        await callback.message.edit_text(
            message_text,
            reply_markup=kb.schedule_week_summary_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в show_schedule_week_summary: {error_details}")
        await callback.answer("❌ Ошибка при загрузке расписания", show_alert=True)

@router.callback_query(F.data == "schedule_week_detailed")
async def show_schedule_week_detailed(callback: CallbackQuery):
    """Показать подробное расписание на неделю"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        week_lessons = await db.get_week_lessons_detailed()
        
        today = get_local_time().date()
        weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        
        message_text = "📅 <b>ПОДРОБНОЕ РАСПИСАНИЕ НА НЕДЕЛЮ</b>\n\n"
        
        if not week_lessons:
            message_text += "✅ На эту неделю занятий нет"
        else:
            # Группируем по дням
            lessons_by_day = {}
            for lesson in week_lessons:
                lesson_date = datetime.strptime(lesson['lesson_date'], '%Y-%m-%d').date()
                date_str = lesson_date.strftime('%d.%m.%Y')
                weekday_name = weekday_names[lesson_date.weekday()]
                
                if date_str not in lessons_by_day:
                    lessons_by_day[date_str] = {
                        'weekday': weekday_name,
                        'lessons': []
                    }
                lessons_by_day[date_str]['lessons'].append(lesson)
            
            # Сортируем дни
            sorted_days = sorted(lessons_by_day.keys(), key=lambda x: datetime.strptime(x, '%d.%m.%Y'))
            
            for date_str in sorted_days:
                day_data = lessons_by_day[date_str]
                weekday_name = day_data['weekday']
                message_text += f"📆 <b>{date_str} ({weekday_name})</b>\n\n"
                
                for lesson in day_data['lessons']:
                    time_str = format_lesson_time(lesson['lesson_time'], lesson.get('duration', 60))
                    
                    # Мини-информация об ученике
                    student_name = lesson['student_name']
                    grade = lesson.get('grade', '')
                    subject = lesson.get('subject', '')
                    student_info = f"{student_name}"
                    if grade:
                        student_info += f" ({grade}кл"
                        if subject:
                            student_info += f", {subject}"
                        student_info += ")"
                    
                    # ДЗ (обрезаем для мобильных)
                    homework = (lesson.get('homework') or '').strip()
                    if len(homework) > 50:
                        homework = homework[:47] + "..."
                    
                    # Цена
                    price = int(lesson.get('price', 0))
                    
                    message_text += f"🕐 <b>{time_str}</b>\n"
                    message_text += f"👤 {student_info}\n"
                    if homework:
                        message_text += f"📝 {homework}\n"
                    message_text += f"💰 {price}₽\n\n"
        
        await callback.message.edit_text(
            message_text,
            reply_markup=kb.schedule_week_detailed_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в show_schedule_week_detailed: {error_details}")
        await callback.answer("❌ Ошибка при загрузке расписания", show_alert=True)

@router.callback_query(F.data.startswith("schedule_"))
async def show_schedule_management(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access_callback(callback):
        return
    
    try:
        student_id = int(callback.data.split("_")[1])
        student = await db.get_student(student_id)
        schedules = await db.get_student_schedules(student_id)
        
        if not student:
            await callback.answer("❌ Ученик не найден", show_alert=True)
            return
        
        await state.set_state(AdminPanelStates.schedule_management)
        await state.update_data(student_id=student_id)
        
        schedule_text = f"📅 <b>Расписание: {student['name']}</b>\n\n"
        
        if schedules:
            weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
            for schedule in schedules:
                day_name = weekday_names[schedule['weekday']]
                format_emoji = "🏠" if schedule['lesson_format'] == "offline" else "💻"
                schedule_text += f"{format_emoji} <b>{day_name} {schedule['time']}</b>\n"
                schedule_text += f"💰 {schedule['price']}₽\n\n"
        else:
            schedule_text += "Расписание пока не настроено"
        
        await callback.message.edit_text(
            schedule_text,
            reply_markup=kb.schedule_management_keyboard(student_id, schedules),
            parse_mode="HTML"
        )
        await safe_callback_answer(callback)
        
    except Exception as e:
        await callback.message.edit_text(
            "❌ Ошибка при загрузке расписания",
            reply_markup=kb.back_to_student_profile(student_id)
        )
        await safe_callback_answer(callback)

@router.callback_query(F.data.startswith("add_schedule_"))
async def start_schedule_creation(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access_callback(callback):
        return
    
    try:
        student_id = int(callback.data.split("_")[2])
        await state.set_state(AdminPanelStates.creating_schedule_weekday)
        await state.update_data(student_id=student_id)
        
        await callback.message.edit_text(
            "📅 <b>Создание расписания</b>\n\nВыберите день недели:",
            reply_markup=kb.weekday_selection_keyboard(student_id),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("weekday_"))
async def process_weekday_selection(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access_callback(callback):
        return
    
    try:
        weekday = int(callback.data.split("_")[1])
        weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        
        await state.update_data(weekday=weekday)
        await state.set_state(AdminPanelStates.creating_schedule_time)
        
        await callback.message.edit_text(
            f"🕐 <b>Создание расписания</b>\n\n"
            f"День: <b>{weekday_names[weekday]}</b>\n\n"
            f"Введите время в формате ЧЧ:ММ (например: 17:30):",
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.message(AdminPanelStates.creating_schedule_time)
async def process_schedule_time(message: Message, state: FSMContext):
    if not await check_admin_access(message):
        return
    
    time_text = message.text.strip()
    
    # Проверяем формат времени
    try:
        datetime.strptime(time_text, '%H:%M')
    except ValueError:
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ:ММ (например: 17:30)")
        return
    
    await state.update_data(time=time_text)
    await state.set_state(AdminPanelStates.creating_schedule_format)
    
    data = await state.get_data()
    weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    
    await message.answer(
        f"🏠 <b>Создание расписания</b>\n\n"
        f"День: <b>{weekday_names[data['weekday']]}</b>\n"
        f"Время: <b>{time_text}</b>\n\n"
        f"Выберите формат занятия:",
        reply_markup=kb.lesson_format_selection_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("format_"), AdminPanelStates.creating_schedule_format)
async def process_format_selection(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access_callback(callback):
        return
    
    lesson_format = callback.data.split("_")[1]  # "offline" или "online"
    await state.update_data(lesson_format=lesson_format)
    await state.set_state(AdminPanelStates.creating_schedule_duration)
    
    format_text = "🏠 Очно" if lesson_format == "offline" else "💻 Онлайн"
    
    data = await state.get_data()
    weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    
    await callback.message.edit_text(
        f"⏰ <b>Создание расписания</b>\n\n"
        f"День: <b>{weekday_names[data['weekday']]}</b>\n"
        f"Время: <b>{data['time']}</b>\n"
        f"Формат: <b>{format_text}</b>\n\n"
        f"Выберите продолжительность занятия:",
        reply_markup=kb.lesson_duration_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(AdminPanelStates.creating_schedule_price)
async def process_schedule_price(message: Message, state: FSMContext):
    """Обработка ручного ввода цены (когда нет настроек или пользователь хочет изменить)"""
    if not await check_admin_access(message):
        await state.clear()
        return
    
    try:
        price = float(message.text.strip().replace(',', '.'))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректную стоимость (положительное число)")
        return
    
    await state.update_data(price=price)
    await show_schedule_confirmation_final(message, state, is_message=True)

@router.callback_query(F.data.startswith("duration_"), AdminPanelStates.creating_schedule_duration)
async def process_duration_selection(callback: CallbackQuery, state: FSMContext):
    if not await check_admin_access_callback(callback):
        return
    
    duration_value = callback.data.split("_")[1]
    
    if duration_value == "custom":
        await state.set_state(AdminPanelStates.creating_schedule_custom_duration)
        await callback.message.edit_text(
            "⏰ <b>Создание расписания</b>\n\n"
            "Введите продолжительность в минутах (например: 75):",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    # Стандартные варианты
    duration = int(duration_value)
    await state.update_data(duration=duration)
    await show_schedule_price_confirmation(callback, state)

@router.message(AdminPanelStates.creating_schedule_custom_duration)
async def process_custom_duration(message: Message, state: FSMContext):
    if not await check_admin_access(message):
        return
    
    try:
        duration = int(message.text.strip())
        if duration <= 0 or duration > 300:  # максимум 5 часов
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректную продолжительность от 1 до 300 минут")
        return
    
    await state.update_data(duration=duration)
    
    # Создаем "фейковый" callback для переиспользования функции подтверждения
    fake_callback = type('FakeCallback', (), {
        'message': message,
        'answer': lambda: None
    })()
    
    await show_schedule_price_confirmation(fake_callback, state, is_message=True)

async def show_schedule_price_confirmation(callback_or_message, state: FSMContext, is_message=False):
    """Показать расчет цены и подтверждение при создании расписания"""
    data = await state.get_data()
    student_id = data['student_id']
    student = await db.get_student(student_id)
    
    if not student:
        if is_message:
            await callback_or_message.answer("❌ Ученик не найден")
        else:
            await callback_or_message.answer("❌ Ученик не найден", show_alert=True)
        return
    
    # Рассчитываем цену за час
    lesson_format = data['lesson_format']
    grade = student['grade'] or 9
    subject = student.get('subject', '')
    custom_price = student.get('custom_price_per_hour')
    
    price_per_hour = await db.calculate_price(grade, subject, lesson_format, custom_price)
    
    if price_per_hour <= 0:
        # Нет настроек цен - запрашиваем вручную
        await state.set_state(AdminPanelStates.creating_schedule_price)
        weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        format_text = "🏠 Очно" if lesson_format == "offline" else "💻 Онлайн"
        duration = data['duration']
        duration_text = "1 час" if duration == 60 else "1.5 часа" if duration == 90 else f"{duration//60} часа" if duration >= 120 else f"{duration} минут"
        
        text = (
            f"💰 <b>Создание расписания</b>\n\n"
            f"День: <b>{weekday_names[data['weekday']]}</b>\n"
            f"Время: <b>{data['time']}</b>\n"
            f"Формат: <b>{format_text}</b>\n"
            f"Продолжительность: <b>{duration_text}</b>\n\n"
            f"⚠️ Настройки цен не заполнены. Введите стоимость занятия в рублях:"
        )
        
        if is_message:
            await callback_or_message.answer(text, parse_mode="HTML", reply_markup=kb.back_to_student_profile(student_id))
        else:
            await callback_or_message.message.edit_text(text, parse_mode="HTML", reply_markup=kb.back_to_student_profile(student_id))
            await callback_or_message.answer()
        return
    
    # Рассчитываем итоговую цену (цена за час × продолжительность в часах)
    duration = data['duration']
    hours = duration / 60.0
    total_price = price_per_hour * hours
    
    # Сохраняем цену в state
    await state.update_data(price=total_price, price_per_hour=price_per_hour)
    
    # Форматируем продолжительность
    if duration == 60:
        duration_text = "1 час"
    elif duration == 90:
        duration_text = "1.5 часа"
    elif duration == 120:
        duration_text = "2 часа"
    else:
        duration_text = f"{duration} минут"
    
    weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    format_text = "🏠 Очно" if lesson_format == "offline" else "💻 Онлайн"
    
    price_source = "индивидуальная цена" if custom_price else "настройки"
    
    confirmation_text = (
        f"💰 <b>Цена занятия</b>\n\n"
        f"👤 <b>Ученик:</b> {student['name']}\n"
        f"📅 <b>День:</b> {weekday_names[data['weekday']]}\n"
        f"🕐 <b>Время:</b> {data['time']}\n"
        f"📍 <b>Формат:</b> {format_text}\n"
        f"⏰ <b>Продолжительность:</b> {duration_text}\n\n"
        f"💵 <b>Цена:</b> {int(total_price)}₽ ({int(price_per_hour)}₽/час × {hours:.1f}ч)\n"
        f"ℹ️ Источник: {price_source}\n\n"
        f"Подтвердить цену или изменить?"
    )
    
    await state.set_state(AdminPanelStates.creating_schedule_price)
    
    if is_message:
        await callback_or_message.answer(
            confirmation_text,
            reply_markup=kb.confirm_price_keyboard(total_price, student_id=student_id),
            parse_mode="HTML"
        )
    else:
        await callback_or_message.message.edit_text(
            confirmation_text,
            reply_markup=kb.confirm_price_keyboard(total_price, student_id=student_id),
            parse_mode="HTML"
        )
        await callback_or_message.answer()

# Обработчики подтверждения/изменения цены при создании расписания
@router.callback_query(F.data.startswith("confirm_price_schedule_"))
async def confirm_price_schedule(callback: CallbackQuery, state: FSMContext):
    """Подтвердить цену и перейти к финальному подтверждению расписания"""
    if not await check_admin_access_callback(callback):
        return
    
    await show_schedule_confirmation_final(callback, state, is_message=False)

@router.callback_query(F.data.startswith("change_price_schedule_"))
async def change_price_schedule(callback: CallbackQuery, state: FSMContext):
    """Изменить цену вручную"""
    if not await check_admin_access_callback(callback):
        return
    
    data = await state.get_data()
    student_id = data['student_id']
    weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    format_text = "🏠 Очно" if data['lesson_format'] == "offline" else "💻 Онлайн"
    duration = data['duration']
    duration_text = "1 час" if duration == 60 else "1.5 часа" if duration == 90 else f"{duration//60} часа" if duration >= 120 else f"{duration} минут"
    
    await callback.message.edit_text(
        f"💰 <b>Изменение цены</b>\n\n"
        f"День: <b>{weekday_names[data['weekday']]}</b>\n"
        f"Время: <b>{data['time']}</b>\n"
        f"Формат: <b>{format_text}</b>\n"
        f"Продолжительность: <b>{duration_text}</b>\n\n"
        f"Введите новую стоимость занятия в рублях:",
        parse_mode="HTML",
        reply_markup=kb.back_to_student_profile(student_id)
    )
    await callback.answer()

async def show_schedule_confirmation_final(callback_or_message, state: FSMContext, is_message=False):
    """Показать финальное подтверждение создания расписания"""
    data = await state.get_data()
    weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    format_text = "📍 Очно" if data['lesson_format'] == "offline" else "💻 Онлайн"
    
    duration = data['duration']
    if duration == 60:
        duration_text = "1 час"
    elif duration == 90:
        duration_text = "1.5 часа"
    elif duration == 120:
        duration_text = "2 часа"
    else:
        duration_text = f"{duration} минут"
    
    student = await db.get_student(data['student_id'])
    
    confirmation_text = (
        f"✅ <b>Подтверждение создания расписания</b>\n\n"
        f"👤 <b>Ученик:</b> {student['name']}\n"
        f"📅 <b>День:</b> {weekday_names[data['weekday']]}\n"
        f"🕐 <b>Время:</b> {data['time']}\n"
        f"📍 <b>Формат:</b> {format_text}\n"
        f"💰 <b>Стоимость:</b> {int(data['price'])}₽\n"
        f"⏰ <b>Продолжительность:</b> {duration_text}\n\n"
        f"Создать расписание?"
    )
    
    await state.set_state(AdminPanelStates.creating_schedule_confirmation)
    
    if is_message:
        await callback_or_message.answer(
            confirmation_text,
            reply_markup=kb.schedule_confirmation_keyboard(data['student_id']),
            parse_mode="HTML"
        )
    else:
        await callback_or_message.message.edit_text(
            confirmation_text,
            reply_markup=kb.schedule_confirmation_keyboard(data['student_id']),
            parse_mode="HTML"
        )
        await callback_or_message.answer()

# Обновляем подтверждение создания расписания
@router.callback_query(F.data.startswith("confirm_schedule_"))
async def confirm_schedule_creation(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not await check_admin_access_callback(callback):
        return
    
    try:
        data = await state.get_data()
        
        # Создаем расписание с продолжительностью
        schedule_id = await db.create_schedule(
            student_id=data['student_id'],
            weekday=data['weekday'],
            time=data['time'],
            lesson_format=data['lesson_format'],
            price=data['price'],
            duration=data['duration'],
            subject=None
        )
        
        if schedule_id:
            # Форматируем продолжительность для отображения
            duration = data['duration']
            if duration == 60:
                duration_text = "1 час"
            elif duration == 90:
                duration_text = "1.5 часа"
            elif duration == 120:
                duration_text = "2 часа"
            else:
                duration_text = f"{duration} мин"
            
            # Получаем информацию об ученике для уведомления
            student = await db.get_student(data['student_id'])
            weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
            format_text = "онлайн" if data['lesson_format'] == 'online' else "оффлайн"
            
            # 🆕 АВТОМАТИЧЕСКАЯ ГЕНЕРАЦИЯ ЗАНЯТИЙ СРАЗУ ПОСЛЕ СОЗДАНИЯ РАСПИСАНИЯ
            created_count = 0
            created_dates = []
            try:
                # Получаем расписание
                schedule = {
                    'id': schedule_id,
                    'student_id': data['student_id'],
                    'weekday': data['weekday'],
                    'time': data['time']
                }
                
                # Генерируем даты занятий на 4 недели вперед
                today = get_local_time()
                dates = []
                
                days_ahead = data['weekday'] - today.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                
                next_date = today + timedelta(days=days_ahead)
                
                for i in range(4):  # 4 недели
                    dates.append(next_date.strftime('%Y-%m-%d'))
                    next_date += timedelta(weeks=1)
                
                # Создаем занятия
                from bot_template.database.task_manager import TaskManager
                task_manager = TaskManager(db)
                
                for lesson_date in dates:
                    if not await db.lesson_exists(data['student_id'], lesson_date, data['time']):
                        lesson_id = await db.create_lesson_from_schedule(schedule_id, lesson_date)
                        if lesson_id:
                            created_count += 1
                            created_dates.append(lesson_date)
                            
                            # Создаем задачи уведомлений для нового занятия
                            try:
                                lesson = await db.get_lesson_by_id(lesson_id)
                                if lesson:
                                    await task_manager.schedule_lesson_tasks(lesson, days_ahead=30)
                            except Exception as task_error:
                                logger.warning(f" Ошибка создания задач для занятия #{lesson_id}: {task_error}")
                
            except Exception as gen_error:
                logger.error(f"Ошибка при автогенерации занятий: {gen_error}")
            
            # Отправляем уведомление ученику
            notification_text = (
                f"📅 <b>Новое расписание создано</b>\n\n"
                f"📆 День недели: {weekday_names[data['weekday']]}\n"
                f"🕐 Время: {data['time']}\n"
                f"📍 Формат: {format_text}\n"
                f"⏰ Продолжительность: {duration_text}\n"
                f"💰 Стоимость: {int(data['price'])}₽\n"
            )
            
            if created_count > 0:
                notification_text += f"\n📚 Создано занятий: {created_count}\n"
                # Показываем первые несколько дат
                if created_dates:
                    dates_list = "\n".join([format_date_with_weekday(d, full_format=True) for d in created_dates[:5]])
                    notification_text += f"\n📅 Ближайшие занятия:\n{dates_list}"
                    if created_count > 5:
                        notification_text += f"\n... и еще {created_count - 5} занятий"
            
            try:
                await bot.send_message(
                    chat_id=data['student_id'],
                    text=notification_text,
                    parse_mode="HTML"
                )
                logger.info(f" Отправлено уведомление ученику {student['name']} о создании расписания")
            except Exception as e:
                logger.warning(f" Не удалось отправить уведомление ученику {data['student_id']}: {e}")
                
            await callback.message.edit_text(
                f"✅ <b>Расписание успешно создано!</b>\n\n"
                f"⏰ Продолжительность: {duration_text}\n"
                f"📅 Автоматически создано занятий: {created_count}\n\n"
                f"Новые занятия будут создаваться автоматически.",
                reply_markup=kb.back_to_student_profile(data['student_id']),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                "❌ Ошибка при создании расписания",
                reply_markup=kb.back_to_student_profile(data['student_id'])
            )
        
        await state.clear()
        await callback.answer()
        
    except Exception as e:
        await callback.answer("❌ Ошибка при создании расписания", show_alert=True)

@router.callback_query(F.data.startswith("modify_duration_"))
async def modify_schedule_duration(callback: CallbackQuery):
    """Начать изменение продолжительности"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        schedule_id = int(callback.data.split("_")[2])
        
        await callback.message.edit_text(
            "⏰ <b>Изменение продолжительности</b>\n\n"
            "Выберите новую продолжительность:",
            reply_markup=kb.lesson_duration_edit_keyboard(schedule_id),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("edit_duration_"))
async def update_schedule_duration_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обновить продолжительность расписания"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        parts = callback.data.split("_")
        duration_value = parts[2]
        schedule_id = int(parts[3])
        
        if duration_value == "custom":
            await state.set_state(AdminPanelStates.editing_schedule_custom_duration)
            await state.update_data(editing_schedule_id=schedule_id)
            
            await callback.message.edit_text(
                "⏰ <b>Изменение продолжительности</b>\n\n"
                "Введите новую продолжительность в минутах (например: 75):",
                parse_mode="HTML"
            )
            await callback.answer()
            return
        
        # Получаем старое расписание
        old_schedule = await db.get_schedule(schedule_id)
        if not old_schedule:
            await callback.answer("❌ Расписание не найдено", show_alert=True)
            return
        
        # Стандартные варианты
        duration = int(duration_value)
        success = await db.update_schedule_duration(schedule_id, duration)
        
        if success:
            # Пересоздаем будущие занятия
            await db.recreate_future_lessons_from_schedule(schedule_id)
            
            # Получаем новое расписание
            new_schedule = await db.get_schedule(schedule_id)
            
            # Отправляем уведомление ученику
            if new_schedule:
                await send_schedule_change_notification(bot, old_schedule['student_id'], old_schedule, new_schedule)
            
            if duration == 60:
                duration_text = "1 час"
            elif duration == 90:
                duration_text = "1.5 часа"
            elif duration == 120:
                duration_text = "2 часа"
            else:
                duration_text = f"{duration} мин"
                
            await callback.message.edit_text(
                f"✅ <b>Продолжительность изменена!</b>\n\n"
                f"Новая продолжительность: <b>{duration_text}</b>\n\n"
                f"Будущие занятия обновлены автоматически.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ К расписанию", callback_data=f"edit_schedule_item_{schedule_id}")]
                ]),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                "❌ Ошибка при изменении продолжительности",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data=f"edit_schedule_item_{schedule_id}")]
                ])
            )
        
        await callback.answer()
        
    except Exception as e:
        import traceback
        logger.error(f"Ошибка в update_schedule_duration_handler: {traceback.format_exc()}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router.message(AdminPanelStates.editing_schedule_custom_duration)
async def update_custom_duration(message: Message, state: FSMContext, bot: Bot):
    """Обновить пользовательскую продолжительность"""
    if not await check_admin_access(message):
        return
    
    try:
        duration = int(message.text.strip())
        if duration <= 0 or duration > 300:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректную продолжительность от 1 до 300 минут")
        return
    
    try:
        data = await state.get_data()
        schedule_id = data['editing_schedule_id']
        
        # Получаем старое расписание
        old_schedule = await db.get_schedule(schedule_id)
        if not old_schedule:
            await message.answer("❌ Расписание не найдено")
            await state.clear()
            return
        
        success = await db.update_schedule_duration(schedule_id, duration)
        
        if success:
            # Пересоздаем будущие занятия
            await db.recreate_future_lessons_from_schedule(schedule_id)
            
            # Получаем новое расписание
            new_schedule = await db.get_schedule(schedule_id)
            
            # Отправляем уведомление ученику
            if new_schedule:
                await send_schedule_change_notification(bot, old_schedule['student_id'], old_schedule, new_schedule)
            await message.answer(
                f"✅ <b>Продолжительность изменена!</b>\n\n"
                f"Новая продолжительность: <b>{duration} минут</b>\n\n"
                f"Будущие занятия обновлены автоматически.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ К расписанию", callback_data=f"edit_schedule_item_{schedule_id}")]
                ]),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ Ошибка при изменении продолжительности",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data=f"edit_schedule_item_{schedule_id}")]
                ])
            )
        
        await state.clear()
        
    except Exception as e:
        await message.answer("❌ Произошла ошибка")
        await state.clear()

@router.callback_query(F.data == "back_to_admin")
async def back_to_admin_menu(callback: CallbackQuery, state: FSMContext):
    # Проверка прав
    if not  await check_admin_access_callback(callback):
        return
    await state.clear()
    await state.set_state(AdminPanelStates.panel)
    await callback.message.delete()
    await callback.message.answer(
        "👨‍🏫 Вы вернулись в главное меню\n\n"
        "Выберите действие:",
        reply_markup=kb.admin_main,
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_admin_main")
async def back_to_admin_main(callback: CallbackQuery, state: FSMContext):
    """Вернуться в главное меню админ-панели"""
    if not await check_admin_access_callback(callback):
        return
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        "👨‍🏫 Вы вернулись в главное меню\n\n"
        "Выберите действие:",
        reply_markup=kb.admin_main,
        parse_mode="HTML"
    )
    await callback.answer()

# === СОЗДАНИЕ ЗАНЯТИЯ ВНЕ РАСПИСАНИЯ ===

@router.callback_query(F.data.startswith("add_manual_lesson_"))
async def add_manual_lesson_start(callback: CallbackQuery, state: FSMContext):
    """Начать создание занятия вне расписания"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        student_id = int(callback.data.split("_")[3])
        student = await db.get_student(student_id)
        
        if not student:
            await callback.answer("❌ Ученик не найден", show_alert=True)
            return
        
        await state.set_state(AdminPanelStates.creating_lesson_date)
        await state.update_data(student_id=student_id)

        now = get_local_time()
        calendar_kb = kb.calendar_keyboard(
            year=now.year,
            month=now.month,
            context="cl",
            extra_data=f"s{student_id}"
        )

        await callback.message.edit_text(
            f"➕ <b>ДОБАВЛЕНИЕ ЗАНЯТИЯ</b>\n\n"
            f"👤 Ученик: <b>{student['name']}</b>\n\n"
            f"📅 <b>Выберите дату занятия:</b>",
            reply_markup=calendar_kb,
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.message(AdminPanelStates.creating_lesson_date)
async def process_lesson_date(message: Message, state: FSMContext):
    """Обработка текста в состоянии выбора даты — направляем к календарю"""
    if not await check_admin_access(message):
        await state.clear()
        return

    data = await state.get_data()
    student_id = data.get("student_id")
    await message.answer(
        "📅 Пожалуйста, выберите дату из календаря выше ☝️"
    )

@router.message(AdminPanelStates.creating_lesson_time)
async def process_lesson_time(message: Message, state: FSMContext):
    """Обработка времени занятия"""
    if not await check_admin_access(message):
        await state.clear()
        return
    
    try:
        time_text = message.text.strip()
        
        # Проверяем формат времени
        try:
            time_obj = datetime.strptime(time_text, '%H:%M')
            lesson_time = time_obj.strftime('%H:%M')
        except ValueError:
            await message.answer(
                "❌ Неверный формат времени!\n\n"
                "Введите время в формате ЧЧ:ММ (например: 18:00):"
            )
            return
        
        data = await state.get_data()
        student_id = data.get('student_id')
        lesson_date = data.get('lesson_date')
        
        # Проверяем, не существует ли уже занятие на это время
        if await db.lesson_exists(student_id, lesson_date, lesson_time):
            await message.answer(
                "❌ Занятие на эту дату и время уже существует!\n\n"
                "Введите другое время:"
            )
            return
        
        await state.update_data(lesson_time=lesson_time)
        await state.set_state(AdminPanelStates.creating_lesson_format)
        
        await message.answer(
            f"✅ Время: <b>{lesson_time}</b>\n\n"
            f"📍 Выберите формат занятия:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                *kb.lesson_format_selection_keyboard().inline_keyboard,
                [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"view_student_{student_id}")]
            ]),
            parse_mode="HTML"
        )
        
    except Exception as e:
        await message.answer("❌ Ошибка при обработке времени. Попробуйте снова:")

@router.callback_query(AdminPanelStates.creating_lesson_format, F.data.startswith("format_"))
async def process_lesson_format(callback: CallbackQuery, state: FSMContext):
    """Обработка формата занятия"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        format_type = callback.data.split("_")[1]
        
        await state.update_data(lesson_format=format_type)
        await state.set_state(AdminPanelStates.creating_lesson_duration)
        
        data = await state.get_data()
        student_id = data.get('student_id')
        format_text = "онлайн" if format_type == "online" else "оффлайн"
        
        await callback.message.edit_text(
            f"✅ Формат: <b>{format_text}</b>\n\n"
            f"⏰ Выберите продолжительность занятия:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                *kb.lesson_duration_keyboard().inline_keyboard,
                [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"view_student_{student_id}")]
            ]),
                parse_mode="HTML"
            )
        await callback.answer()
        
    except Exception as e:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(AdminPanelStates.creating_lesson_duration, F.data.startswith("duration_"))
async def process_lesson_duration(callback: CallbackQuery, state: FSMContext):
    """Обработка продолжительности занятия"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        data = await state.get_data()
        student_id = data.get('student_id')
        
        if callback.data == "duration_custom":
            await state.set_state(AdminPanelStates.creating_lesson_custom_duration)
            await callback.message.edit_text(
                "✏️ Введите продолжительность в минутах (от 30 до 300):",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"view_student_{student_id}")]
                ])
            )
            await callback.answer()
            return
        
        duration = int(callback.data.split("_")[1])
        await state.update_data(duration=duration)
        await show_lesson_price_confirmation(callback, state, is_callback=True)
        
    except Exception as e:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.message(AdminPanelStates.creating_lesson_custom_duration)
async def process_lesson_custom_duration(message: Message, state: FSMContext):
    """Обработка пользовательской продолжительности"""
    if not await check_admin_access(message):
        await state.clear()
        return
    
    try:
        duration = int(message.text.strip())
        
        if duration < 30 or duration > 300:
            await message.answer("❌ Продолжительность должна быть от 30 до 300 минут!")
        return
        
        await state.update_data(duration=duration)
        
        # Создаем "фейковый" callback для переиспользования функции
        fake_callback = type('FakeCallback', (), {
            'message': message,
            'answer': lambda: None
        })()
        
        await show_lesson_price_confirmation(fake_callback, state, is_callback=False)
        
    except ValueError:
        await message.answer("❌ Введите число от 30 до 300!")
    except Exception as e:
        await message.answer("❌ Ошибка при обработке продолжительности")

async def show_lesson_price_confirmation(callback_or_message, state: FSMContext, is_callback=True):
    """Показать расчет цены и подтверждение при создании урока"""
    data = await state.get_data()
    student_id = data.get('student_id')
    student = await db.get_student(student_id)
    
    if not student:
        if is_callback:
            await callback_or_message.answer("❌ Ученик не найден", show_alert=True)
        else:
            await callback_or_message.answer("❌ Ученик не найден")
        return
    
    # Рассчитываем цену за час
    lesson_format = data.get('lesson_format')
    grade = student['grade'] or 9
    subject = student.get('subject', '')
    custom_price = student.get('custom_price_per_hour')
    
    price_per_hour = await db.calculate_price(grade, subject, lesson_format, custom_price)
    
    if price_per_hour <= 0:
        # Нет настроек цен - запрашиваем вручную
        await state.set_state(AdminPanelStates.creating_lesson_price)
        duration = data.get('duration', 60)
        duration_text = "1 час" if duration == 60 else "1.5 часа" if duration == 90 else f"{duration//60} часа" if duration >= 120 else f"{duration} минут"
        format_text = "🏠 Очно" if lesson_format == "offline" else "💻 Онлайн"
        
        text = (
            f"💰 <b>Создание занятия</b>\n\n"
            f"📅 Дата: <b>{data.get('lesson_date', '')}</b>\n"
            f"🕐 Время: <b>{data.get('lesson_time', '')}</b>\n"
            f"📍 Формат: <b>{format_text}</b>\n"
            f"⏰ Продолжительность: <b>{duration_text}</b>\n\n"
            f"⚠️ Настройки цен не заполнены. Введите стоимость занятия в рублях:"
        )
        
        if is_callback:
            await callback_or_message.message.edit_text(text, parse_mode="HTML", reply_markup=kb.back_to_student_profile(student_id))
            await callback_or_message.answer()
        else:
            await callback_or_message.answer(text, parse_mode="HTML", reply_markup=kb.back_to_student_profile(student_id))
        return
    
    # Рассчитываем итоговую цену
    duration = data.get('duration', 60)
    hours = duration / 60.0
    total_price = price_per_hour * hours
    
    # Сохраняем цену в state
    await state.update_data(price=total_price, price_per_hour=price_per_hour)
    
    # Форматируем продолжительность
    if duration == 60:
        duration_text = "1 час"
    elif duration == 90:
        duration_text = "1.5 часа"
    elif duration == 120:
        duration_text = "2 часа"
    else:
        duration_text = f"{duration} минут"
    
    format_text = "🏠 Очно" if lesson_format == "offline" else "💻 Онлайн"
    price_source = "индивидуальная цена" if custom_price else "настройки"
    
    confirmation_text = (
        f"💰 <b>Цена занятия</b>\n\n"
        f"👤 <b>Ученик:</b> {student['name']}\n"
        f"📅 <b>Дата:</b> {data.get('lesson_date', '')}\n"
        f"🕐 <b>Время:</b> {data.get('lesson_time', '')}\n"
        f"📍 <b>Формат:</b> {format_text}\n"
        f"⏰ <b>Продолжительность:</b> {duration_text}\n\n"
        f"💵 <b>Цена:</b> {int(total_price)}₽ ({int(price_per_hour)}₽/час × {hours:.1f}ч)\n"
        f"ℹ️ Источник: {price_source}\n\n"
        f"Подтвердить цену или изменить?"
    )
    
    await state.set_state(AdminPanelStates.creating_lesson_price)
    
    if is_callback:
        await callback_or_message.message.edit_text(
            confirmation_text,
            reply_markup=kb.confirm_price_keyboard(total_price, student_id=student_id, is_lesson=True),
            parse_mode="HTML"
        )
        await callback_or_message.answer()
    else:
        await callback_or_message.answer(
            confirmation_text,
            reply_markup=kb.confirm_price_keyboard(total_price, student_id=student_id, is_lesson=True),
            parse_mode="HTML"
        )

# Обработчики подтверждения/изменения цены при создании урока
@router.callback_query(F.data.startswith("confirm_new_lesson_price_"))
async def confirm_new_lesson_price(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтвердить цену и создать новый урок"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        # Создаем урок напрямую
        await process_lesson_price_from_state(callback, state, bot, is_callback=True)
        await callback.answer()
    except Exception as e:
        import traceback
        logger.error(f" Ошибка в confirm_new_lesson_price: {traceback.format_exc()}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.callback_query(F.data.startswith("change_new_lesson_price_"))
async def change_new_lesson_price(callback: CallbackQuery, state: FSMContext):
    """Изменить цену нового урока вручную"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        data = await state.get_data()
        student_id = data.get('student_id')
        if not student_id:
            await callback.answer("❌ Ошибка: не найден ID ученика", show_alert=True)
            return
        
        duration = data.get('duration', 60)
        duration_text = "1 час" if duration == 60 else "1.5 часа" if duration == 90 else f"{duration//60} часа" if duration >= 120 else f"{duration} минут"
        format_text = "🏠 Очно" if data.get('lesson_format') == "offline" else "💻 Онлайн"
        
        await callback.message.edit_text(
            f"💰 <b>Изменение цены</b>\n\n"
            f"📅 Дата: <b>{data.get('lesson_date', '')}</b>\n"
            f"🕐 Время: <b>{data.get('lesson_time', '')}</b>\n"
            f"📍 Формат: <b>{format_text}</b>\n"
            f"⏰ Продолжительность: <b>{duration_text}</b>\n\n"
            f"Введите новую стоимость занятия в рублях:",
            parse_mode="HTML",
            reply_markup=kb.back_to_student_profile(student_id)
        )
        await callback.answer()
    except Exception as e:
        import traceback
        logger.error(f" Ошибка в change_new_lesson_price: {traceback.format_exc()}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.callback_query(F.data.startswith("confirm_price_lesson_"))
async def confirm_price_lesson(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтвердить цену и обновить существующий урок (если понадобится в будущем)"""
    if not await check_admin_access_callback(callback):
        return
    
    # Пока не используется, но оставляем для обратной совместимости
    await callback.answer("❌ Функция не реализована", show_alert=True)

@router.callback_query(F.data.startswith("change_price_lesson_"))
async def change_price_lesson(callback: CallbackQuery, state: FSMContext):
    """Изменить цену существующего урока (если понадобится в будущем)"""
    if not await check_admin_access_callback(callback):
        return
    
    # Пока не используется, но оставляем для обратной совместимости
    await callback.answer("❌ Функция не реализована", show_alert=True)

@router.message(AdminPanelStates.creating_lesson_price)
async def process_lesson_price(message: Message, state: FSMContext, bot: Bot):
    """Обработка цены и создание занятия"""
    if not await check_admin_access(message):
        await state.clear()
        return
    
    try:
        price = float(message.text.strip().replace(',', '.'))
        
        if price <= 0:
            await message.answer("❌ Стоимость должна быть больше нуля!")
            return
        
        await state.update_data(price=price)
        await process_lesson_price_from_state(message, state, bot, is_callback=False)
        
    except ValueError:
        await message.answer("❌ Введите корректную стоимость (число)")

async def process_lesson_price_from_state(callback_or_message, state: FSMContext, bot: Bot, is_callback=False):
    """Создать урок из данных в state"""
    try:
        data = await state.get_data()
        student_id = data.get('student_id')
        lesson_date = data.get('lesson_date')
        lesson_time = data.get('lesson_time')
        lesson_format = data.get('lesson_format')
        duration = data.get('duration', 60)
        price = data.get('price')
        
        if not price or price <= 0:
            if is_callback:
                await callback_or_message.answer("❌ Цена не указана", show_alert=True)
            else:
                await callback_or_message.answer("❌ Цена не указана")
            return
        
        # Получаем информацию об ученике
        student = await db.get_student(student_id)
        subject = student.get('subject') if student else None
        
        # Создаем занятие
        lesson_id = await db.add_lesson(
            student_id=student_id,
            lesson_date=lesson_date,
            lesson_time=lesson_time,
            subject=subject,
            lesson_format=lesson_format,
            price=price,
            duration=duration
        )
        
        if lesson_id:
            # Создаем задачи уведомлений для нового занятия
            try:
                from bot_template.database.task_manager import TaskManager
                task_manager = TaskManager(db)
                lesson = await db.get_lesson_by_id(lesson_id)
                if lesson:
                    await task_manager.schedule_lesson_tasks(lesson, days_ahead=30)
            except Exception as task_error:
                logger.warning(f" Ошибка создания задач для занятия #{lesson_id}: {task_error}")
            
            # Форматируем данные для уведомления
            date_str = kb.format_date_with_weekday(lesson_date, full_format=True)
            format_text = "онлайн" if lesson_format == "online" else "оффлайн"
            duration_text = f"{duration//60}ч" if duration >= 60 else f"{duration}м"
            if duration == 90:
                duration_text = "1.5ч"
            
            # Отправляем уведомление ученику
            notification_text = (
                f"📚 <b>Новое занятие</b>\n\n"
                f"📅 {date_str}\n"
                f"🕐 {lesson_time}\n"
                f"⏱️ Продолжительность: {duration_text}\n"
                f"📍 Формат: {format_text}\n"
                f"💰 Стоимость: {int(price)}₽"
            )
            
            try:
                await bot.send_message(
                    chat_id=student_id,
                    text=notification_text,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f" Не удалось отправить уведомление ученику {student_id}: {e}")
            
            success_text = (
                f"✅ <b>Занятие успешно создано!</b>\n\n"
                f"📅 {date_str} в {lesson_time}\n"
                f"💰 {int(price)}₽\n\n"
                f"Уведомление отправлено ученику."
            )
            
            if is_callback:
                await callback_or_message.message.edit_text(
                    success_text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="👤 К профилю", callback_data=f"view_student_{student_id}")]
                    ]),
                    parse_mode="HTML"
                )
                await callback_or_message.answer()
            else:
                await callback_or_message.answer(
                    success_text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="👤 К профилю", callback_data=f"view_student_{student_id}")]
                    ]),
                    parse_mode="HTML"
                )
        else:
            error_text = "❌ Ошибка при создании занятия"
            if is_callback:
                await callback_or_message.message.edit_text(error_text)
                await callback_or_message.answer("❌ Ошибка", show_alert=True)
            else:
                await callback_or_message.answer(error_text)
        
        await state.clear()
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в process_lesson_price_from_state: {error_details}")
        error_text = "❌ Произошла ошибка при создании занятия"
        if is_callback:
            await callback_or_message.answer(error_text, show_alert=True)
        else:
            await callback_or_message.answer(error_text)
        await state.clear()

@router.callback_query(F.data.startswith("add_lesson_"))
async def add_lesson_start(callback: CallbackQuery):
    # Проверка прав
    if not  await check_admin_access_callback(callback):
        return
    
    await callback.answer(
        "➕ Используйте кнопку '➕ Добавить занятие' в профиле ученика или кнопку '➕ Добавить' в главном меню",
        show_alert=True
    )

@router.callback_query(F.data.startswith("edit_student_"))
async def edit_student_start(callback: CallbackQuery):
    """Показать меню редактирования профиля ученика"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        student_id = int(callback.data.split("_")[2])
        student = await db.get_student(student_id)
        
        if not student:
            await callback.answer("❌ Ученик не найден", show_alert=True)
            return
        
        # Формируем текст профиля (для учителя направление показывается всегда)
        profile_text = f"✏️ <b>РЕДАКТИРОВАНИЕ ПРОФИЛЯ</b>\n\n"
        profile_text += f"👤 <b>Ученик:</b> {student['name']}\n"
        profile_text += f"🎓 Класс: {student['grade']}\n"
        profile_text += f"📊 Направление: {student.get('subject', 'не указано')}\n"
        profile_text += f"📞 Телефон: {student['phone']}\n"
        profile_text += f"📅 Зарегистрирован: {student['registration_date']}\n\n"
        profile_text += f"Что хотите изменить?"
        
        await callback.message.edit_text(
            profile_text,
            reply_markup=kb.admin_edit_student_profile_keyboard(student_id),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в edit_student_start: {error_details}")
        await callback.answer("❌ Ошибка при загрузке профиля", show_alert=True)

# === ОБРАБОТЧИКИ РЕДАКТИРОВАНИЯ ПРОФИЛЯ УЧЕНИКА УЧИТЕЛЕМ ===

@router.callback_query(F.data.startswith("admin_change_name_"))
async def admin_change_name_start(callback: CallbackQuery, state: FSMContext):
    """Начать изменение имени ученика"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        student_id = int(callback.data.split("_")[3])
        student = await db.get_student(student_id)
        
        if not student:
            await callback.answer("❌ Ученик не найден", show_alert=True)
            return
        
        await state.set_state(AdminPanelStates.editing_student_name)
        await state.update_data(student_id=student_id)
        
        await callback.message.edit_text(
            f"✏️ <b>Изменение имени</b>\n\n"
            f"Текущее имя: <b>{student['name']}</b>\n\n"
            f"Введите новое имя:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"edit_student_{student_id}")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.message(AdminPanelStates.editing_student_name)
async def admin_change_name_finish(message: Message, state: FSMContext):
    """Завершить изменение имени ученика"""
    if not await check_admin_access(message):
        await state.clear()
        return
    
    try:
        new_name = message.text.strip()
        
        if len(new_name) < 2:
            await message.answer("❌ Имя слишком короткое! Попробуйте снова:")
            return
        
        data = await state.get_data()
        student_id = data.get('student_id')
        
        if not student_id:
            await message.answer("❌ Ошибка: ID ученика не найден")
            await state.clear()
            return
        
        student = await db.get_student(student_id)
        old_name = student['name'] if student else ""
        
        success, can_notify = await db.update_student_name(student_id, new_name, changed_by='teacher')
        
        # Отправляем уведомление ученику, если это первое изменение сегодня
        if can_notify and student:
            notification_text = (
                f"📝 <b>Изменение данных профиля</b>\n\n"
                f"Имя изменено:\n"
                f"Было: {old_name}\n"
                f"Стало: {new_name}"
            )
            try:
                await message.bot.send_message(
                    chat_id=student_id,
                    text=notification_text,
                    parse_mode="HTML"
                )
                logger.info(f" Отправлено уведомление ученику {student_id} об изменении имени")
            except Exception as e:
                logger.warning(f" Не удалось отправить уведомление ученику {student_id}: {e}")
        
        await message.answer(
            f"✅ Имя успешно изменено на: <b>{new_name}</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👤 К профилю", callback_data=f"view_student_{student_id}")]
            ]),
            parse_mode="HTML"
        )
        await state.clear()
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в admin_change_name_finish: {error_details}")
        await message.answer("❌ Произошла ошибка при изменении имени")
        await state.clear()

@router.callback_query(F.data.startswith("admin_change_grade_"))
async def admin_change_grade_start(callback: CallbackQuery, state: FSMContext):
    """Начать изменение класса ученика"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        student_id = int(callback.data.split("_")[3])
        student = await db.get_student(student_id)
        
        if not student:
            await callback.answer("❌ Ученик не найден", show_alert=True)
            return
        
        await state.set_state(AdminPanelStates.editing_student_grade)
        await state.update_data(student_id=student_id)
        
        await callback.message.edit_text(
            f"🎓 <b>Изменение класса</b>\n\n"
            f"Текущий класс: <b>{student['grade']}</b>\n\n"
            f"Выберите новый класс:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                *kb.number_class.inline_keyboard,
                [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"edit_student_{student_id}")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(AdminPanelStates.editing_student_grade, F.data.startswith("class_"))
async def admin_change_grade_finish(callback: CallbackQuery, state: FSMContext):
    """Завершить изменение класса ученика"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        new_grade = int(callback.data.split("_")[1])
        data = await state.get_data()
        student_id = data.get('student_id')
        
        if not student_id:
            await callback.answer("❌ Ошибка: ID ученика не найден", show_alert=True)
            await state.clear()
            return
        
        student = await db.get_student(student_id)
        old_grade = student['grade'] if student else 0
        
        success, can_notify = await db.update_student_grade(student_id, new_grade, changed_by='teacher')
        
        # Отправляем уведомление ученику, если это первое изменение сегодня
        if can_notify and student:
            notification_text = (
                f"📝 <b>Изменение данных профиля</b>\n\n"
                f"Класс изменен:\n"
                f"Было: {old_grade}\n"
                f"Стало: {new_grade}"
            )
            try:
                await callback.bot.send_message(
                    chat_id=student_id,
                    text=notification_text,
                    parse_mode="HTML"
                )
                logger.info(f" Отправлено уведомление ученику {student_id} об изменении класса")
            except Exception as e:
                logger.warning(f" Не удалось отправить уведомление ученику {student_id}: {e}")
        
        await callback.message.edit_text(
            f"✅ Класс успешно изменен на: <b>{new_grade}</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👤 К профилю", callback_data=f"view_student_{student_id}")]
            ]),
            parse_mode="HTML"
        )
        await state.clear()
        await callback.answer()
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в admin_change_grade_finish: {error_details}")
        await callback.answer("❌ Ошибка при изменении класса", show_alert=True)
        await state.clear()

@router.callback_query(F.data.startswith("admin_change_subject_"))
async def admin_change_subject_start(callback: CallbackQuery, state: FSMContext):
    """Начать изменение направления ученика"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        student_id = int(callback.data.split("_")[3])
        student = await db.get_student(student_id)
        
        if not student:
            await callback.answer("❌ Ученик не найден", show_alert=True)
            return
        
        await state.set_state(AdminPanelStates.editing_student_subject)
        await state.update_data(student_id=student_id)
        
        current_subject = student.get('subject', 'не указано')
        
        await callback.message.edit_text(
            f"📊 <b>Изменение направления</b>\n\n"
            f"Текущее направление: <b>{current_subject}</b>\n\n"
            f"Выберите новое направление:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                *kb.var.inline_keyboard,
                [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"edit_student_{student_id}")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(AdminPanelStates.editing_student_subject, F.data.in_(["base", "profil"]))
async def admin_change_subject_finish(callback: CallbackQuery, state: FSMContext):
    """Завершить изменение направления ученика"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        new_subject = "База" if callback.data == "base" else "Профиль"
        data = await state.get_data()
        student_id = data.get('student_id')
        
        if not student_id:
            await callback.answer("❌ Ошибка: ID ученика не найден", show_alert=True)
            await state.clear()
            return
        
        student = await db.get_student(student_id)
        old_subject = student.get('subject', 'не указано') if student else "не указано"
        
        success, can_notify = await db.update_student_subject(student_id, new_subject, changed_by='teacher')
        
        # Отправляем уведомление ученику, если это первое изменение сегодня
        if can_notify and student:
            notification_text = (
                f"📝 <b>Изменение данных профиля</b>\n\n"
                f"Направление изменено:\n"
                f"Было: {old_subject}\n"
                f"Стало: {new_subject}"
            )
            try:
                await callback.bot.send_message(
                    chat_id=student_id,
                    text=notification_text,
                    parse_mode="HTML"
                )
                logger.info(f" Отправлено уведомление ученику {student_id} об изменении направления")
            except Exception as e:
                logger.warning(f" Не удалось отправить уведомление ученику {student_id}: {e}")
        
        await callback.message.edit_text(
            f"✅ Направление успешно изменено на: <b>{new_subject}</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👤 К профилю", callback_data=f"view_student_{student_id}")]
            ]),
            parse_mode="HTML"
        )
        await state.clear()
        await callback.answer()
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в admin_change_subject_finish: {error_details}")
        await callback.answer("❌ Ошибка при изменении направления", show_alert=True)
        await state.clear()

@router.callback_query(F.data.startswith("confirm_delete_student_"))
async def confirm_delete_student(callback: CallbackQuery):
    """Подтверждение удаления ученика"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        student_id = int(callback.data.split("_")[3])
        
        # Получаем данные ученика
        student = await db.get_student(student_id)
        if not student:
            await callback.answer("❌ Ученик не найден", show_alert=True)
            return
        
        # Подсчитываем связанные данные
        schedules = await db.get_student_schedules(student_id)
        lessons = await db.get_lessons_by_student(student_id)
        
        confirmation_text = (
            f"⚠️ <b>ВНИМАНИЕ! Удаление ученика</b>\n\n"
            f"👤 <b>Ученик:</b> {student['name']}\n"
            f"📊 <b>Будет удалено:</b>\n"
            f"• Профиль ученика\n"
            f"• Расписание ({len(schedules)} записей)\n"
            f"• Уроки ({len(lessons)} записей)\n"
            f"• История изменений\n\n"
            f"<b>Это действие нельзя отменить!</b>\n\n"
            f"Вы уверены, что хотите удалить этого ученика?"
        )
        
        await callback.message.edit_text(
            confirmation_text,
            reply_markup=kb.student_delete_confirmation_keyboard(student_id),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в confirm_delete_student: {error_details}")
        await callback.answer("❌ Ошибка при загрузке данных", show_alert=True)

@router.callback_query(F.data.startswith("delete_student_confirmed_"))
async def delete_student_confirmed(callback: CallbackQuery):
    """Выполнение удаления ученика"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        student_id = int(callback.data.split("_")[3])
        
        # Получаем данные ученика перед удалением
        student = await db.get_student(student_id)
        if not student:
            await callback.answer("❌ Ученик не найден", show_alert=True)
            return
        
        student_name = student['name']
        
        # Удаляем ученика и все связанные данные
        success = await db.delete_student(student_id)
        
        if success:
            await callback.message.edit_text(
                f"✅ <b>Ученик удален</b>\n\n"
                f"👤 <b>Удален:</b> {student_name}\n\n"
                f"Все связанные данные (расписание, уроки, история) также удалены.",
                reply_markup=kb.back_to_admin_button(),
                parse_mode="HTML"
            )
            await callback.answer("✅ Ученик успешно удален", show_alert=True)
        else:
            await callback.message.edit_text(
                "❌ Ошибка при удалении ученика",
                reply_markup=kb.back_to_admin_button()
            )
            await callback.answer("❌ Ошибка при удалении", show_alert=True)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в delete_student_confirmed: {error_details}")
        await callback.answer("❌ Произошла ошибка при удалении", show_alert=True)
        await callback.message.edit_text(
            "❌ Произошла ошибка при удалении ученика",
            reply_markup=kb.back_to_admin_button()
        )

@router.callback_query(F.data.startswith("student_custom_price_"))
async def show_student_custom_price(callback: CallbackQuery, state: FSMContext):
    """Показать/установить индивидуальную цену для ученика"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        student_id = int(callback.data.split("_")[3])
        student = await db.get_student(student_id)
        
        if not student:
            await callback.answer("❌ Ученик не найден", show_alert=True)
            return
        
        custom_price = student.get('custom_price_per_hour')
        
        if custom_price:
            # Показываем текущую индивидуальную цену
            text = (
                f"💰 <b>Индивидуальная цена ученика</b>\n\n"
                f"👤 <b>Ученик:</b> {student['name']}\n"
                f"💵 <b>Текущая цена:</b> {int(custom_price)}₽/час\n\n"
                f"Что хотите сделать?"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✏️ Изменить цену", callback_data=f"edit_custom_price_{student_id}")],
                [InlineKeyboardButton(text="🗑️ Удалить индивидуальную цену", callback_data=f"remove_custom_price_{student_id}")],
                [InlineKeyboardButton(text="◀️ К профилю", callback_data=f"view_student_{student_id}")]
            ])
        else:
            # Нет индивидуальной цены - предлагаем установить
            # Рассчитываем текущую цену по настройкам
            grade = student.get('grade') or 9
            subject = student.get('subject', '')
            # Берем формат из регистрации или используем online по умолчанию
            lesson_format = student.get('registration_format', 'online') or 'online'
            
            calculated_price = await db.calculate_price(grade, subject, lesson_format, None)
            
            text = (
                f"💰 <b>Индивидуальная цена ученика</b>\n\n"
                f"👤 <b>Ученик:</b> {student['name']}\n"
                f"📚 <b>Класс:</b> {grade}\n"
                f"🎯 <b>Направление:</b> {subject or 'не указано'}\n\n"
            )
            
            if calculated_price > 0:
                text += (
                    f"💵 <b>Текущая цена (из настроек):</b> {int(calculated_price)}₽/час\n\n"
                    f"Вы можете установить индивидуальную цену для этого ученика, которая будет использоваться вместо цены из настроек."
                )
            else:
                text += (
                    f"⚠️ Настройки цен не заполнены.\n\n"
                    f"Вы можете установить индивидуальную цену для этого ученика."
                )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Установить индивидуальную цену", callback_data=f"set_custom_price_{student_id}")],
                [InlineKeyboardButton(text="◀️ К профилю", callback_data=f"view_student_{student_id}")]
            ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в show_student_custom_price: {error_details}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.callback_query(F.data.startswith("set_custom_price_") | F.data.startswith("edit_custom_price_"))
async def start_set_custom_price(callback: CallbackQuery, state: FSMContext):
    """Начать установку/изменение индивидуальной цены"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        student_id = int(callback.data.split("_")[3])
        student = await db.get_student(student_id)
        
        if not student:
            await callback.answer("❌ Ученик не найден", show_alert=True)
            return
        
        await state.set_state(AdminPanelStates.setting_student_custom_price)
        await state.update_data(student_id=student_id)
        
        current_price = student.get('custom_price_per_hour')
        if current_price:
            text = (
                f"✏️ <b>Изменение индивидуальной цены</b>\n\n"
                f"👤 <b>Ученик:</b> {student['name']}\n"
                f"💵 <b>Текущая цена:</b> {int(current_price)}₽/час\n\n"
                f"💰 Введите новую цену за час (в рублях):"
            )
        else:
            text = (
                f"💰 <b>Установка индивидуальной цены</b>\n\n"
                f"👤 <b>Ученик:</b> {student['name']}\n\n"
                f"💰 Введите цену за час (в рублях):"
            )
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"student_custom_price_{student_id}")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в start_set_custom_price: {error_details}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.message(AdminPanelStates.setting_student_custom_price)
async def process_custom_price(message: Message, state: FSMContext):
    """Обработка ввода индивидуальной цены"""
    if not await check_admin_access(message):
        await state.clear()
        return
    
    try:
        price = float(message.text.strip().replace(',', '.'))
        if price <= 0:
            raise ValueError
        
        data = await state.get_data()
        student_id = data.get('student_id')
        
        if not student_id:
            await message.answer("❌ Ошибка: ID ученика не найден")
            await state.clear()
            return
        
        student = await db.get_student(student_id)
        if not student:
            await message.answer("❌ Ученик не найден")
            await state.clear()
            return
        
        # Устанавливаем индивидуальную цену
        success = await db.set_student_custom_price(student_id, price)
        
        if success:
            await message.answer(
                f"✅ <b>Индивидуальная цена установлена!</b>\n\n"
                f"👤 <b>Ученик:</b> {student['name']}\n"
                f"💵 <b>Цена:</b> {int(price)}₽/час\n\n"
                f"Эта цена будет использоваться при создании расписания и занятий для этого ученика.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="👤 К профилю", callback_data=f"view_student_{student_id}")]
                ]),
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Ошибка при установке цены", reply_markup=kb.back_to_admin_button())
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите корректную цену (положительное число)")
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в process_custom_price: {error_details}")
        await message.answer("❌ Произошла ошибка", reply_markup=kb.back_to_admin_button())
        await state.clear()

@router.callback_query(F.data.startswith("remove_custom_price_"))
async def remove_custom_price(callback: CallbackQuery):
    """Удалить индивидуальную цену ученика"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        student_id = int(callback.data.split("_")[3])
        student = await db.get_student(student_id)
        
        if not student:
            await callback.answer("❌ Ученик не найден", show_alert=True)
            return
        
        # Удаляем индивидуальную цену
        success = await db.set_student_custom_price(student_id, None)
        
        if success:
            await callback.message.edit_text(
                f"✅ <b>Индивидуальная цена удалена</b>\n\n"
                f"👤 <b>Ученик:</b> {student['name']}\n\n"
                f"Теперь для этого ученика будет использоваться цена из настроек.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="👤 К профилю", callback_data=f"view_student_{student_id}")]
                ]),
                parse_mode="HTML"
            )
            await callback.answer("✅ Индивидуальная цена удалена", show_alert=True)
        else:
            await callback.message.edit_text(
                "❌ Ошибка при удалении индивидуальной цены",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="👤 К профилю", callback_data=f"view_student_{student_id}")]
                ])
            )
            await callback.answer("❌ Ошибка", show_alert=True)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в remove_custom_price: {error_details}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        f"👋 Добро пожаловать обратно!\n\n"
        f"Используйте меню ниже для выбора действий.\n"
        f'Посмотри на панель снизу и выбери нужный вариант! 📚✨',
        reply_markup=kb.main
    )
    await callback.answer()


@router.message(F.text == '💰 Узнать цену своего первого занятия')
async def first_price(message: Message, state: FSMContext):
    """Узнать цену первого занятия для новых пользователей"""
    user_id = message.from_user.id
    user_name = message.from_user.username

    # Проверяем, зарегистрирован ли пользователь
    student = await db.get_student(user_id)

    if student:
        # Пользователь уже зарегистрирован
        await message.reply(
            f"👋 Ты уже зарегестрирован, {user_name}!\n\n"
            "Используй меню ниже для выбора действий.",
            reply_markup=kb.main
        )
    else:
        # Пользователь не зарегистрирован
        await state.set_state(Reg.userFormat)
        await message.answer(
            '🎯 Отлично! Чтобы подобрать для тебя идеальное предложение, '
            'я должен узнать тебя получше.\n\n'
            '📝 Для начала выбери формат обучения:',
            reply_markup=kb.format
        )
    

@router.message(F.text == 'Мое расписание')
async def my_schedule(message: Message):
    """Показать расписание занятий ученика"""
    user_id = message.from_user.id

    student = await db.get_student(user_id)
    if not student:
        await message.answer("❌ Вы не зарегистрированы!")
        return

    lessons = await db.get_lessons_by_student(user_id)

    if not lessons:
        await message.answer(
            "📅 У вас пока нет запланированных занятий.\n"
            "Обратитесь к репетитору для записи."
        )
        return

    text = "📚 Ваши занятия:\n\n"
    for lesson in lessons:
        status_emoji = {
            'scheduled': '⏳',
            'completed': '✅',
            'cancelled': '❌'
        }.get(lesson.get('status', 'scheduled'), '❓')

        text += (
            f"{status_emoji} {lesson.get('lesson_date', 'Дата не указана')} "
            f"в {lesson.get('lesson_time', 'Время не указано')}\n"
            f"📚 {lesson.get('subject', 'Предмет не указан')}\n"
            f"💰 {lesson.get('price', 0)} руб.\n\n"
        )

    await message.answer(text)

@router.message(F.text == 'Доп. материал')
async def dop_material(message: Message):
    """Дополнительные материалы"""
    await message.reply(
        # '📚 Дополнительные материалы\n\n'
        # 'Выбери свое направление:\n\n'
        # 'ОГЭ/ЕГЭ',
        f'В разработке...',
        #reply_markup=kb.dop_material if hasattr(kb, 'dop_material') else None
    )

@router.message(F.text == "Мой профиль")
async def profile_setting(message: Message):
    student_id = message.from_user.id

    student = await db.get_student(student_id)
    
    # Проверяем возможность изменения каждого параметра
    can_change_name, last_name_change = await db.can_change_parameter(student_id, 'name')
    can_change_grade, last_grade_change = await db.can_change_parameter(student_id, 'grade')
    can_change_subject, last_subject_change = await db.can_change_parameter(student_id, 'subject')
    
    # Формируем текст профиля
    profile_text = f"👤 <b>Мой профиль</b>\n\n"
    profile_text += f"✏️ Имя: {student['name']}\n"
    profile_text += f"🎓 Класс: {student['grade']}\n"
    
    # Показываем направление только для классов >= 10
    if student['grade'] >= 10:
        profile_text += f"📊 Направление: {student['subject']}\n"
    
    profile_text += f"📞 Телефон: {student['phone']}\n"
    profile_text += f"📅 Зарегистрирован: {student['registration_date']}\n\n"
    
    # Добавляем информацию об ограничениях
    profile_text += "ℹ️ <i>Каждый параметр можно менять один раз в неделю</i>"
    
    await message.reply(
        profile_text,
        reply_markup=kb.profile_change_keyboard(student['grade']),
        parse_mode="HTML"
    )
#Смена имени
@router.callback_query(F.data == "change_name")
async def change_name_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    # Проверяем, можно ли изменить имя (один раз в неделю)
    can_change, last_change = await db.can_change_parameter(user_id, 'name')
    
    if not can_change:
        # Форматируем дату последнего изменения
        try:
            date_obj = datetime.strptime(last_change, '%Y-%m-%d %H:%M:%S')
            date_str = date_obj.strftime('%d.%m.%Y %H:%M')
        except:
            date_str = last_change
        
        await callback.message.edit_text(
            f"❌ <b>Имя уже изменялось на этой неделе</b>\n\n"
            f"📅 Последнее изменение: {date_str}\n\n"
            f"ℹ️ Каждый параметр можно менять один раз в неделю.",
            reply_markup=kb.back_button,
            parse_mode="HTML"
        )
        await callback.answer("⚠️ Имя уже изменялось на этой неделе", show_alert=True)
        return
    
    await callback.message.edit_text(
        "✏️ Введите новое имя:",
        reply_markup=kb.back_button
    )
    await state.set_state(Reg.change_name)
    await callback.answer()

@router.message(Reg.change_name)
async def change_name_finish(message: Message, state: FSMContext):
    new_name = message.text.strip()
    
    if len(new_name) < 2:
        await message.answer("❌ Имя слишком короткое! Попробуйте снова:")
        return
    
    user_id = message.from_user.id
    student = await db.get_student(user_id)
    old_name = student['name'] if student else ""
    
    # Проверяем еще раз перед сохранением
    can_change, last_change = await db.can_change_parameter(user_id, 'name')
    if not can_change:
        await message.answer(
            f"❌ Имя уже изменялось на этой неделе.\n"
            f"Каждый параметр можно менять один раз в неделю.",
            reply_markup=kb.main
        )
        await state.clear()
        return
    
    success, can_notify = await db.update_student_name(user_id, new_name)
    
    if not success:
        await message.answer("❌ Ошибка при сохранении имени", reply_markup=kb.main)
        await state.clear()
        return
    
    # Отправляем уведомление учителю, если это первое изменение сегодня
    # ВРЕМЕННО ОТКЛЮЧЕНО: уведомления об изменении данных профиля
    # if can_notify and student:
    #     notification_text = (
    #         f"📝 <b>Изменение данных ученика</b>\n\n"
    #         f"👤 Ученик: {student['name']}\n"
    #         f"Имя изменено:\n"
    #         f"Было: {old_name}\n"
    #         f"Стало: {new_name}"
    #     )
    #     try:
    #         await message.bot.send_message(
    #             chat_id=TUTOR_ID,
    #             text=notification_text,
    #             parse_mode="HTML"
    #         )
    #         logger.info(f" Отправлено уведомление учителю об изменении имени ученика {user_id}")
    #     except Exception as e:
    #         logger.warning(f" Не удалось отправить уведомление учителю: {e}")
    
    await message.answer(
        f"✅ Имя успешно изменено на: {new_name}",
        reply_markup=kb.main
    )
    await state.clear()


#Смена класса
@router.callback_query(F.data == "change_grade")
async def change_grade_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    # Проверяем, можно ли изменить класс (один раз в неделю)
    can_change, last_change = await db.can_change_parameter(user_id, 'grade')
    
    if not can_change:
        # Форматируем дату последнего изменения
        try:
            date_obj = datetime.strptime(last_change, '%Y-%m-%d %H:%M:%S')
            date_str = date_obj.strftime('%d.%m.%Y %H:%M')
        except:
            date_str = last_change
        
        await callback.message.edit_text(
            f"❌ <b>Класс уже изменялся на этой неделе</b>\n\n"
            f"📅 Последнее изменение: {date_str}\n\n"
            f"ℹ️ Каждый параметр можно менять один раз в неделю.",
            reply_markup=kb.back_button,
            parse_mode="HTML"
        )
        await callback.answer("⚠️ Класс уже изменялся на этой неделе", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📚 Выберите новый класс:",
        reply_markup=kb.number_class
    )
    await state.set_state(Reg.change_grade)
    await callback.answer()

@router.callback_query(Reg.change_grade, F.data.startswith("class_"))
async def change_grade_finish(callback: CallbackQuery, state: FSMContext):
    new_grade = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    # Получаем старый класс ученика
    student = await db.get_student(user_id)
    old_grade = student['grade'] if student else 0
    
    # Проверяем еще раз перед сохранением
    can_change, last_change = await db.can_change_parameter(user_id, 'grade')
    if not can_change:
        await callback.message.edit_text(
            f"❌ Класс уже изменялся на этой неделе.\n"
            f"Каждый параметр можно менять один раз в неделю.",
            reply_markup=kb.back_button
        )
        await callback.answer("⚠️ Класс уже изменялся на этой неделе", show_alert=True)
        await state.clear()
        return
    
    # Обновляем класс
    success, can_notify = await db.update_student_grade(user_id, new_grade)
    
    if not success:
        await callback.message.edit_text("❌ Ошибка при сохранении класса", reply_markup=kb.back_button)
        await callback.answer()
        await state.clear()
        return
    
    # Отправляем уведомление учителю, если это первое изменение сегодня
    # ВРЕМЕННО ОТКЛЮЧЕНО: уведомления об изменении данных профиля
    # if can_notify and student:
    #     notification_text = (
    #         f"📝 <b>Изменение данных ученика</b>\n\n"
    #         f"👤 Ученик: {student['name']}\n"
    #         f"Класс изменен:\n"
    #         f"Было: {old_grade}\n"
    #         f"Стало: {new_grade}"
    #     )
    #     try:
    #         await callback.bot.send_message(
    #             chat_id=TUTOR_ID,
    #             text=notification_text,
    #             parse_mode="HTML"
    #         )
    #         logger.info(f" Отправлено уведомление учителю об изменении класса ученика {user_id}")
    #     except Exception as e:
    #         logger.warning(f" Не удалось отправить уведомление учителю: {e}")
    
    # Если класс стал >= 10 и был < 10, предлагаем выбрать направление
    if new_grade >= 10 and old_grade < 10:
        await callback.message.edit_text(
            f"✅ Класс успешно изменен на: {new_grade}\n\n"
            f"📊 Теперь вы можете выбрать направление:",
            reply_markup=kb.var
        )
        await state.set_state(Reg.change_subject)
        await callback.answer()
        return
    
    # Если класс стал < 10 и был >= 10, направление не показывается в профиле (но остается в БД для учителя)
    if new_grade < 10 and old_grade >= 10:
        await callback.message.edit_text(
            f"✅ Класс успешно изменен на: {new_grade}\n\n"
            f"ℹ️ Направление скрыто из профиля"
        )
        await callback.message.answer(
            "Ваш профиль обновлён!",
            reply_markup=kb.main
        )
        await state.clear()
        await callback.answer()
        return
    
    # Если класс >= 10 и был >= 10, просто обновляем
    await callback.message.edit_text(
        f"✅ Класс успешно изменен на: {new_grade}"
    )
    await callback.message.answer(
        "Ваш профиль обновлён!",
        reply_markup=kb.main
    )
    await state.clear()
    await callback.answer()

#Смена профиля
@router.callback_query(F.data == "change_profil")
async def change_subject_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    # Проверяем, можно ли изменить направление (один раз в неделю)
    can_change, last_change = await db.can_change_parameter(user_id, 'subject')
    
    if not can_change:
        # Форматируем дату последнего изменения
        try:
            date_obj = datetime.strptime(last_change, '%Y-%m-%d %H:%M:%S')
            date_str = date_obj.strftime('%d.%m.%Y %H:%M')
        except:
            date_str = last_change
        
        await callback.message.edit_text(
            f"❌ <b>Направление уже изменялось на этой неделе</b>\n\n"
            f"📅 Последнее изменение: {date_str}\n\n"
            f"ℹ️ Каждый параметр можно менять один раз в неделю.",
            reply_markup=kb.back_button,
            parse_mode="HTML"
        )
        await callback.answer("⚠️ Направление уже изменялось на этой неделе", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📈 Выберите новое направление:",
        reply_markup=kb.var
    )
    await state.set_state(Reg.change_subject)
    await callback.answer()

@router.callback_query(Reg.change_subject, F.data.in_(["base", "profil"]))
async def change_subject_finish(callback: CallbackQuery, state: FSMContext):
    new_subject = "База" if callback.data == "base" else "Профиль"
    user_id = callback.from_user.id
    
    student = await db.get_student(user_id)
    old_subject = student.get('subject', 'не указано') if student else "не указано"
    
    # Проверяем еще раз перед сохранением
    can_change, last_change = await db.can_change_parameter(user_id, 'subject')
    if not can_change:
        await callback.message.edit_text(
            f"❌ Направление уже изменялось на этой неделе.\n"
            f"Каждый параметр можно менять один раз в неделю.",
            reply_markup=kb.back_button
        )
        await callback.answer("⚠️ Направление уже изменялось на этой неделе", show_alert=True)
        await state.clear()
        return
    
    success, can_notify = await db.update_student_subject(user_id, new_subject)
    
    if not success:
        await callback.message.edit_text("❌ Ошибка при сохранении направления", reply_markup=kb.back_button)
        await callback.answer()
        await state.clear()
        return
    
    # Отправляем уведомление учителю, если это первое изменение сегодня
    # ВРЕМЕННО ОТКЛЮЧЕНО: уведомления об изменении данных профиля
    # if can_notify and student:
    #     notification_text = (
    #         f"📝 <b>Изменение данных ученика</b>\n\n"
    #         f"👤 Ученик: {student['name']}\n"
    #         f"Направление изменено:\n"
    #         f"Было: {old_subject}\n"
    #         f"Стало: {new_subject}"
    #     )
    #     try:
    #         await callback.bot.send_message(
    #             chat_id=TUTOR_ID,
    #             text=notification_text,
    #             parse_mode="HTML"
    #         )
    #         logger.info(f" Отправлено уведомление учителю об изменении направления ученика {user_id}")
    #     except Exception as e:
    #         logger.warning(f" Не удалось отправить уведомление учителю: {e}")
    
    await callback.message.edit_text(
        f"✅ Направление успешно изменено на: {new_subject}"
    )
    await callback.message.answer(
        "Ваш профиль обновлён!",
        reply_markup=kb.main
    )
    await state.clear()
    await callback.answer()



@router.callback_query(Reg.userFormat, F.data.startswith("format_"))
async def format_select(callback: CallbackQuery, state: FSMContext):
    """Выбор формата обучения"""
    format_type = callback.data.split('_')[1]
    await state.update_data(userFormat=format_type)
    format_emoji = "💻" if format_type == 'online' else "🏫"
    await callback.message.edit_text(
        f"{format_emoji} Формат: {'Онлайн' if format_type == 'online' else 'Оффлайн'}\n\n"
        "📚 Теперь выбери свой класс:",
        reply_markup=kb.number_class
    )
    await state.set_state(Reg.userClass)
    await callback.answer()

@router.callback_query(Reg.userClass, F.data.startswith("class_"))
async def class_select(callback: CallbackQuery, state: FSMContext):
    """Выбор класса"""
    class_num = callback.data.split('_')[1]
    await state.update_data(userClass=class_num)
    data = await state.get_data()
    format_type = data.get('userFormat', 'offline')
    lesson_format = 'online' if format_type == 'online' else 'offline'
    grade = int(class_num)

    # Для классов 5-9 не запрашиваем направление
    if 5 <= int(class_num) <= 9:
        await state.update_data(userVar="base")
        # Рассчитываем цену: 5-9 класс, база
        subject = "базовый уровень"
        price_per_hour = await db.calculate_price(grade, subject, lesson_format)
        
        if price_per_hour <= 0:
            # Нет настроек - используем старые константы как fallback
            price = ONLINE if format_type == 'online' else OFFLINE
            if grade == 9:
                price += CLASS_9
        else:
            price = price_per_hour
        
        await state.update_data(price=price)
        await callback.message.edit_text(
            f"🎓 Выбран {class_num} класс\n"
            f"💵 Стоимость: {int(price)} руб.\n\n"
            "✏️ Если хочешь записаться на занятие, напиши свое имя:"
        )
        await state.set_state(Reg.userName)
    # Для классов 10-11 запрашиваем направление
    else:
        await callback.message.edit_text(
            f"🎓 Выбран {class_num} класс\n"
            "📊 Теперь выбери направление:",
            reply_markup=kb.var
        )
        await state.set_state(Reg.userVar)
    await callback.answer()

@router.callback_query(Reg.userVar, F.data.in_(['base', 'profil']))
async def var_select(callback: CallbackQuery, state: FSMContext):
    """Выбор направления (база/профиль)"""
    select_var = callback.data
    await state.update_data(userVar=select_var)
    data = await state.get_data()
    format_type = data.get('userFormat', 'offline')
    lesson_format = 'online' if format_type == 'online' else 'offline'
    grade = int(data.get('userClass', 9))
    
    # Определяем subject для расчета цены
    if select_var == 'profil':
        subject = "профильный уровень"
    else:
        subject = "базовый уровень"
    
    # Рассчитываем цену из настроек
    price_per_hour = await db.calculate_price(grade, subject, lesson_format)
    
    if price_per_hour <= 0:
        # Нет настроек - используем старые константы как fallback
        price = ONLINE if format_type == 'online' else OFFLINE
        if grade >= 10:
            price += CLASS_10_11
        elif grade == 9:
            price += CLASS_9
        if select_var == 'profil':
            price += PROFIL
    else:
        price = price_per_hour

    await state.update_data(price=price)
    direction_emoji = "📈" if select_var == 'profil' else "📐"
    await callback.message.edit_text(
        f"{direction_emoji} Направление: {'Профиль' if select_var == 'profil' else 'База'}\n"
        f"💵 Итоговая стоимость: {int(price)} руб.\n\n"
        "👤 Если хотите записаться на занятие, введите ваше ФИО:"
    )
    await state.set_state(Reg.userName)
    await callback.answer()

@router.message(Reg.userName)
async def process_name(message: Message, state: FSMContext):
    """Получение имени пользователя"""
    await state.update_data(userName=message.text)
    await message.answer(
        '📝 Отлично! Теперь введите ваш номер телефона:\n\n'
        '📞 Формат: +79123456789 или 89123456789\n\n'
        'Мы свяжемся с вами для подтверждения записи! ✅'
    )
    await state.set_state(Reg.userNumber)

@router.message(Reg.userNumber)
async def process_phone(message: Message, state: FSMContext, bot: Bot):
    """Получение номера телефона"""
    phone = message.text.strip()

    # Валидация номера телефона
    if not (phone.startswith('+7') or phone.startswith('8')) or len(phone) < 11 or len(phone) > 13:
        await message.answer('❌ Пожалуйста, введите номер в правильном формате: +79123456789 или 89123456789')
        return

    await state.update_data(userNumber=phone)
    await message.answer(
        "📢 Последний вопрос!\n\n"
        "Откуда вы узнали о репетиторе?",
        reply_markup=kb.feedback_keyboard
    )
    await state.set_state(Reg.feedback)

@router.callback_query(Reg.feedback, F.data.startswith("feedback_"))
async def process_feedback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработка выбора источника информации"""
    feedback_type = callback.data.split('_')[1]
    await callback.answer()

    # Если выбран вариант "Другое", запрашиваем текстовый ответ
    if feedback_type == "other":
        await callback.message.edit_text(
            "📝 Пожалуйста, уточните, откуда вы узнали о репетиторе:"
        )
        return

    # Для остальных вариантов сохраняем выбранный вариант
    feedback_mapping = {
        "friends": "От друзей/знакомых",
        "social": "Из ТикТок'а",
        "search": "Поиск в интернете"
    }
    feedback_text = feedback_mapping.get(feedback_type, "")

    await finish_registration(callback, state, bot, feedback_text)

@router.message(Reg.feedback)
async def process_feedback_text(message: Message, state: FSMContext, bot: Bot):
    """Обработка текстового ответа об источнике"""
    feedback_text = message.text
    await finish_registration(message, state, bot, feedback_text)

async def finish_registration(event, state: FSMContext, bot: Bot, feedback_text: str):
    """Завершение регистрации и сохранение в БД"""
    await state.update_data(feedback=feedback_text)
    data = await state.get_data()

    # Определяем, callback это или message
    if isinstance(event, CallbackQuery):
        user = event.from_user
        is_callback = True
    else:
        user = event.from_user
        is_callback = False

    # Получаем данные
    username = f"@{user.username}" if user.username else None
    user_id = user.id
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()

    # Сохраняем в БД
    subject_mapping = {
        "base": "базовый уровень",
        "profil": "профильный уровень"
    }
    subject = subject_mapping.get(data['userVar'], "Математика")
    
    # Сохраняем информацию о регистрации
    registration_format = data['userFormat']  # online/offline
    registration_price = float(data['price'])
    
    await db.add_student(
        user_id=user_id,
        name=data['userName'],
        username=username,
        phone=data['userNumber'],
        grade=int(data['userClass']),
        subject=subject,
        registration_format=registration_format,
        registration_price=registration_price,
        registration_feedback=feedback_text,
        telegram_full_name=full_name
    )

    # Отправляем короткое уведомление репетитору
    short_notification = f"🆕 Появилась новая регистрация: {data['userName']}"
    await bot.send_message(chat_id=TUTOR_ID, text=short_notification)

    # Завершаем регистрацию
    success_message = (
        "🎉 Поздравляем! Регистрация завершена! ✅\n\n"
        "📞 Репетитор свяжется с вами в ближайшее время.\n\n"
        "📚 Ждем вас на занятии! Удачи в изучении математики! ✨"
    )



    if is_callback:
        await event.message.edit_text(success_message)
        await event.message.answer(
            f"👋 Добро пожаловать в главное меню!\n\n"
            "Используйте меню ниже для выбора действий.",
            reply_markup=kb.main
        )
    else:
        await event.answer(success_message)
        await event.answer(
            f"👋 Добро пожаловать в главное меню!\n\n"
            "Используйте меню ниже для выбора действий.",
            reply_markup=kb.main
        )

    await state.clear()

@router.message(Command('help'))
async def cmd_help(message: Message):
    """Команда помощи"""
    await message.answer(
        '📚 <b>Справка по использованию бота</b>\n\n'
        '<b>Основные функции:</b>\n\n'
        '👤 <b>Для учеников:</b>\n'
        '• 📚 Мои занятия - просмотр запланированных занятий\n'
        '• 📖 ДЗ - просмотр домашних заданий (прошлая и текущая неделя)\n'
        '• Мой профиль - редактирование данных (имя, класс, направление)\n'
        '• Доп. материал - дополнительные материалы для подготовки\n\n'
        '👨‍🏫 <b>Для учителя:</b>\n'
        '• 📅 Расписание - просмотр и управление расписанием\n'
        '• 👥 Мои ученики - список всех учеников\n'
        '• 🆕 Новые ученики - новые зарегистрированные ученики\n'
        '• 💰 Должники - список учеников с задолженностью\n'
        '• 📝 Изменения учеников - просмотр изменений профилей\n'
        '• ⚙️ Настройки - настройки бота\n\n'
        '<b>Команды:</b>\n'
        '• /start - Начать работу с ботом\n'
        '• /pn - Открыть админ панель (для учителя)\n'
        '• /help - Показать эту справку\n\n'
        '💡 Используйте кнопки внизу экрана для быстрого доступа к функциям.',
        parse_mode="HTML"
    )

@router.message(F.text == 'Как дела?')
async def how_are_you(message: Message):
    """Ответ на вопрос"""
    await message.answer(
        '✨ У меня все отлично! Готов помочь тебе с математикой!\n\n'
        '📚 Хочешь узнать стоимость занятий или записаться?'
    )

@router.message(Command("get_id"))
async def get_chat_id(message: Message):
    """Получить ID чата и пользователя"""
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else "не указан"
    await message.answer(
        f"📋 Информация о чате:\n"
        f"👤 User ID: {user_id}\n"
        f"🔗 Username: {username}\n"
        f"\nОтправьте этот Chat ID в код как TUTOR_ID"
    )

# === ХЕНДЛЕРЫ ДЛЯ УПРАВЛЕНИЯ ОПЛАТОЙ И ДЗ ===

def format_lesson_ending_message(lesson: Dict) -> str:
    """Формирует текст сообщения об окончании занятия с актуальным статусом оплаты"""
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
    
    return message

@router.callback_query(F.data.startswith("payment_paid_"))
async def handle_payment_paid(callback: CallbackQuery):
    """Отметить занятие как оплаченное"""
    logger.debug(f" Обработчик payment_paid вызван: {callback.data}, user_id: {callback.from_user.id}")
    
    if not await check_admin_access_callback(callback):
        logger.warning(f" Нет доступа для пользователя {callback.from_user.id}")
        return
        
    try:
        lesson_id = int(callback.data.split("_")[-1])
        logger.debug(f" Обработка оплаты для занятия #{lesson_id}")

        lesson = await db.get_lesson_by_id(lesson_id)
        if not lesson:
            logger.error(f" Занятие #{lesson_id} не найдено")
            await callback.answer("❌ Занятие не найдено", show_alert=True)
            return

        # Сохраняем старый статус для проверки, нужно ли отправлять уведомление
        old_payment_status = lesson.get('payment_status', 'unpaid')
        student_id = lesson.get('student_id')
        logger.debug(f" Старый статус оплаты: {old_payment_status}, student_id: {student_id}")

        success = await db.update_lesson_payment_status(lesson_id, 'paid')
        logger.debug(f" Обновление статуса в БД: {'успешно' if success else 'ошибка'}")
        
        if success:
            # Получаем обновленные данные урока
            updated_lesson = await db.get_lesson_by_id(lesson_id)
            if updated_lesson:
                # Получаем имя ученика, если его нет в уроке
                student_id_for_name = updated_lesson.get('student_id')
                if 'student_name' not in updated_lesson and student_id_for_name:
                    student = await db.get_student(student_id_for_name)
                    if student:
                        updated_lesson['student_name'] = student.get('name', 'Неизвестный ученик')
                    else:
                        updated_lesson['student_name'] = 'Неизвестный ученик'
                elif 'student_name' not in updated_lesson:
                    updated_lesson['student_name'] = 'Неизвестный ученик'
                
                # Формируем новое сообщение с актуальным статусом
                new_message = format_lesson_ending_message(updated_lesson)
                logger.debug(f" Формирование нового сообщения для занятия #{lesson_id}")
                
                try:
                    await callback.message.edit_text(
                        new_message,
                        reply_markup=kb.lesson_ending_keyboard(lesson_id, updated_lesson.get('student_id'))
                    )
                    logger.info(f" Сообщение успешно отредактировано")
                except TelegramBadRequest as e:
                    # Если не удалось отредактировать (например, сообщение слишком старое),
                    # отправляем новое сообщение
                    logger.warning(f" Не удалось отредактировать сообщение: {e}")
                    try:
                        await callback.bot.send_message(
                            chat_id=callback.message.chat.id,
                            text=new_message,
                            reply_markup=kb.lesson_ending_keyboard(lesson_id, updated_lesson.get('student_id'))
                        )
                        logger.info(f" Отправлено новое сообщение вместо редактирования")
                    except Exception as send_error:
                        logger.warning(f" Не удалось отправить новое сообщение: {send_error}")
                except Exception as edit_error:
                    logger.warning(f" Ошибка при редактировании сообщения: {edit_error}")
                    # Пробуем отправить новое сообщение
                    try:
                        await callback.bot.send_message(
                            chat_id=callback.message.chat.id,
                            text=new_message,
                            reply_markup=kb.lesson_ending_keyboard(lesson_id, updated_lesson.get('student_id'))
                        )
                    except Exception as send_error:
                        logger.warning(f" Не удалось отправить новое сообщение: {send_error}")
                
                # Отправляем уведомление ученику, если статус изменился на "оплачено"
                if old_payment_status != 'paid' and student_id:
                    try:
                        date_str = format_date_with_weekday(updated_lesson['lesson_date'], full_format=True)
                        notification_text = (
                            f"✅ <b>Занятие оплачено</b>\n\n"
                            f"📅 Дата: {date_str} в {updated_lesson['lesson_time']}\n"
                            f"💰 Сумма: {int(updated_lesson.get('price', 0))}₽"
                        )
                        await callback.bot.send_message(
                            chat_id=student_id,
                            text=notification_text,
                            parse_mode="HTML"
                        )
                        logger.info(f" Отправлено уведомление ученику {student_id} об оплате занятия #{lesson_id}")
                    except Exception as notify_error:
                        logger.warning(f" Не удалось отправить уведомление ученику {student_id}: {notify_error}")
            
            await callback.answer("✅ Занятие отмечено как оплаченное", show_alert=True)
        else:
            logger.error(f" Ошибка обновления статуса в БД")
            await callback.answer("❌ Ошибка обновления статуса", show_alert=True)
    except Exception as e:
        logger.error(f" Критическая ошибка в handle_payment_paid: {e}")
        import traceback
        traceback.print_exc()
        try:
            await callback.answer("❌ Произошла ошибка", show_alert=True)
        except:
            pass

@router.callback_query(F.data.startswith("payment_unpaid_"))
async def handle_payment_unpaid(callback: CallbackQuery):
    """Отметить занятие как неоплаченное"""
    logger.debug(f" Обработчик payment_unpaid вызван: {callback.data}")
    
    if not await check_admin_access_callback(callback):
        logger.warning(f" Нет доступа для пользователя {callback.from_user.id}")
        return
        
    try:
        lesson_id = int(callback.data.split("_")[-1])
        logger.debug(f" Обработка неоплаты для занятия #{lesson_id}")

        lesson = await db.get_lesson_by_id(lesson_id)
        if not lesson:
            logger.error(f" Занятие #{lesson_id} не найдено")
            await callback.answer("❌ Занятие не найдено", show_alert=True)
            return

        success = await db.update_lesson_payment_status(lesson_id, 'unpaid')
        logger.debug(f" Обновление статуса в БД: {'успешно' if success else 'ошибка'}")
        
        if success:
            # Получаем обновленные данные урока
            updated_lesson = await db.get_lesson_by_id(lesson_id)
            if updated_lesson:
                # Получаем имя ученика, если его нет в уроке
                student_id_for_name = updated_lesson.get('student_id')
                if 'student_name' not in updated_lesson and student_id_for_name:
                    student = await db.get_student(student_id_for_name)
                    if student:
                        updated_lesson['student_name'] = student.get('name', 'Неизвестный ученик')
                    else:
                        updated_lesson['student_name'] = 'Неизвестный ученик'
                elif 'student_name' not in updated_lesson:
                    updated_lesson['student_name'] = 'Неизвестный ученик'
                
                # Формируем новое сообщение с актуальным статусом
                new_message = format_lesson_ending_message(updated_lesson)
                logger.debug(f" Формирование нового сообщения для занятия #{lesson_id}")
                
                try:
                    await callback.message.edit_text(
                        new_message,
                        reply_markup=kb.lesson_ending_keyboard(lesson_id, updated_lesson.get('student_id'))
                    )
                    logger.info(f" Сообщение успешно отредактировано")
                except TelegramBadRequest as e:
                    # Если не удалось отредактировать (например, сообщение слишком старое),
                    # отправляем новое сообщение
                    logger.warning(f" Не удалось отредактировать сообщение: {e}")
                    try:
                        await callback.bot.send_message(
                            chat_id=callback.message.chat.id,
                            text=new_message,
                            reply_markup=kb.lesson_ending_keyboard(lesson_id, updated_lesson.get('student_id'))
                        )
                        logger.info(f" Отправлено новое сообщение вместо редактирования")
                    except Exception as send_error:
                        logger.warning(f" Не удалось отправить новое сообщение: {send_error}")
                except Exception as edit_error:
                    logger.warning(f" Ошибка при редактировании сообщения: {edit_error}")
                    # Пробуем отправить новое сообщение
                    try:
                        await callback.bot.send_message(
                            chat_id=callback.message.chat.id,
                            text=new_message,
                            reply_markup=kb.lesson_ending_keyboard(lesson_id, updated_lesson.get('student_id'))
                        )
                    except Exception as send_error:
                        logger.warning(f" Не удалось отправить новое сообщение: {send_error}")
            
            await callback.answer("❌ Занятие отмечено как неоплаченное", show_alert=True)
        else:
            logger.error(f" Ошибка обновления статуса в БД")
            try:
                await callback.answer("❌ Ошибка обновления статуса", show_alert=True)
            except:
                pass
    except Exception as e:
        logger.error(f" Критическая ошибка в handle_payment_unpaid: {e}")
        import traceback
        traceback.print_exc()
        try:
            await callback.answer("❌ Произошла ошибка", show_alert=True)
        except:
            pass

async def _send_homework_notification(bot: Bot, student_id: int, lesson: Dict, homework_text: str, 
                                      old_homework: str, photo_file_id: str = None, file_id: str = None, 
                                      is_editing: bool = False):
    """
    Отправить уведомление ученику о домашнем задании (вариант D: текст отдельно, потом фото и файл)
    """
    student = await db.get_student(student_id)
    date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)
    
    # Формируем текст уведомления
    if is_editing:
        notification_text = (
            f"📝 <b>Изменение домашнего задания</b>\n\n"
            f"📅 Дата занятия: {date_str} в {lesson['lesson_time']}\n\n"
        )
        if old_homework:
            notification_text += f"📖 <b>Было:</b>\n{old_homework}\n\n"
        notification_text += f"📖 <b>Стало:</b>\n{homework_text}"
    else:
        notification_text = (
            f"📝 <b>Новое домашнее задание</b>\n\n"
            f"📅 Дата занятия: {date_str} в {lesson['lesson_time']}\n\n"
            f"📖 <b>Задание:</b>\n{homework_text}"
        )
    
    try:
        # Вариант D: текст отдельным сообщением
        await bot.send_message(
            chat_id=student_id,
            text=notification_text,
            parse_mode="HTML"
        )
        
        # Потом фото (если есть)
        if photo_file_id:
            await bot.send_photo(
                chat_id=student_id,
                photo=photo_file_id
            )
        
        # Потом файл (если есть)
        if file_id:
            await bot.send_document(
                chat_id=student_id,
                document=file_id,
                caption="📎 Файл к домашнему заданию"
            )
        
        action_text = "изменении" if is_editing else "новом"
        attachments = []
        if photo_file_id:
            attachments.append("фото")
        if file_id:
            attachments.append("файл")
        attachment_text = f" с {', '.join(attachments)}" if attachments else ""
        logger.info(f" Отправлено уведомление{attachment_text} ученику {student['name']} об {action_text} домашнем задании")
    except Exception as e:
        logger.warning(f" Не удалось отправить уведомление ученику {student_id}: {e}")

@router.callback_query(F.data.startswith("add_homework_"))
async def handle_add_homework(callback: CallbackQuery, state: FSMContext):
    """Начать процесс добавления домашнего задания"""
    if not await check_admin_access_callback(callback):
        return
        
    lesson_id = int(callback.data.split("_")[-1])

    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.answer("❌ Занятие не найдено", show_alert=True)
        return

    student_id = lesson['student_id']

    next_lesson = await db.get_next_scheduled_lesson(student_id, lesson['lesson_date'], lesson['lesson_time'])
    if not next_lesson:
        await callback.answer("❌ У ученика нет следующего запланированного занятия", show_alert=True)
        return

    next_date = format_date_with_weekday(next_lesson['lesson_date'], full_format=True)

    await state.update_data(
        lesson_id=next_lesson['id'],
        source_lesson_id=lesson_id,
        student_id=student_id,
        source_student_id=student_id,
        next_lesson_date=next_date,
        next_lesson_time=next_lesson['lesson_time']
    )
    await state.set_state(AdminPanelStates.adding_homework)
    
    # Определяем, откуда был вызван обработчик (из уведомления или из истории)
    original_text = callback.message.text or ""
    is_from_history = "📝 <b>Занятие</b>" in original_text or "📝 Занятие" in original_text
    
    # Сохраняем информацию о том, откуда был вызван
    await state.update_data(is_from_history=is_from_history)
    
    # Отправляем новое сообщение вместо редактирования исходного
    cancel_callback = f"edit_payment_{lesson_id}" if is_from_history else f"lesson_ending_{lesson_id}"
    await callback.message.answer(
        "📝 Введите текст домашнего задания для <b>следующего занятия</b>:\n\n"
        f"📅 {next_date} в {next_lesson['lesson_time']}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data=cancel_callback)]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(AdminPanelStates.adding_homework)
async def process_homework_text(message: Message, state: FSMContext, bot: Bot):
    """Обработать текст домашнего задания и спросить про вложения"""
    data = await state.get_data()
    lesson_id = data.get('lesson_id')
    source_lesson_id = data.get('source_lesson_id', lesson_id)
    homework_text = message.text
    
    # Сохраняем текст ДЗ во временное хранилище
    await state.update_data(homework_text=homework_text)
    await state.set_state(AdminPanelStates.adding_homework_photo)
    
    # Спрашиваем про вложения (вариант B)
    await message.answer(
        f"📝 Текст ДЗ сохранен:\n\n{homework_text}\n\n"
        f"📎 Хотите прикрепить фото или файл к домашнему заданию?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📷 Прикрепить фото", callback_data="homework_add_photo"),
                InlineKeyboardButton(text="📎 Прикрепить файл", callback_data="homework_add_file")
            ],
            [
                InlineKeyboardButton(text="📷📎 Прикрепить оба", callback_data="homework_add_both")
            ],
            [
                InlineKeyboardButton(text="⏭️ Пропустить", callback_data="homework_add_photo_no")
            ],
            [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"lesson_ending_{source_lesson_id}")]
        ])
    )

@router.callback_query(F.data == "homework_add_photo")
async def handle_homework_add_photo(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора: прикрепить фото"""
    data = await state.get_data()
    source_lesson_id = data.get('source_lesson_id', data.get('lesson_id'))
    
    # Устанавливаем флаг, что ожидаем фото
    await state.update_data(expecting_attachment="photo")

    await callback.message.edit_text(
        "📷 Отправьте фото для домашнего задания:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Пропустить", callback_data="homework_add_photo_no")],
            [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"lesson_ending_{source_lesson_id}")]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "homework_add_file")
async def handle_homework_add_file(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора: прикрепить файл"""
    data = await state.get_data()
    source_lesson_id = data.get('source_lesson_id', data.get('lesson_id'))
    
    # Устанавливаем флаг, что ожидаем файл
    await state.update_data(expecting_attachment="file")

    await callback.message.edit_text(
        "📎 Отправьте файл для домашнего задания:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Пропустить", callback_data="homework_add_photo_no")],
            [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"lesson_ending_{source_lesson_id}")]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "homework_add_both")
async def handle_homework_add_both(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора: прикрепить оба (вариант C - учитель выбирает порядок)"""
    data = await state.get_data()
    source_lesson_id = data.get('source_lesson_id', data.get('lesson_id'))
    
    # Устанавливаем флаг, что ожидаем оба вложения
    await state.update_data(expecting_attachment="both", attachment_order=None)

    await callback.message.edit_text(
        "📷📎 Выберите, что прикрепить первым:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📷 Сначала фото", callback_data="homework_both_order_photo"),
                InlineKeyboardButton(text="📎 Сначала файл", callback_data="homework_both_order_file")
            ],
            [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"lesson_ending_{source_lesson_id}")]
        ])
    )
    await callback.answer()

@router.callback_query(F.data.startswith("homework_both_order_"))
async def handle_homework_both_order(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора порядка прикрепления (вариант C)"""
    data = await state.get_data()
    source_lesson_id = data.get('source_lesson_id', data.get('lesson_id'))
    
    order = callback.data.replace("homework_both_order_", "")  # "photo" или "file"
    await state.update_data(attachment_order=order, expecting_attachment="both")
    
    if order == "photo":
        text = "📷 Отправьте фото для домашнего задания:\n\nПосле этого будет запрошен файл."
    else:
        text = "📎 Отправьте файл для домашнего задания:\n\nПосле этого будет запрошено фото."
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"lesson_ending_{source_lesson_id}")]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "homework_keep_photo")
async def handle_homework_keep_photo(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик выбора: оставить старое фото (при редактировании)"""
    data = await state.get_data()
    lesson_id = data.get('lesson_id')
    homework_text = data.get('homework_text')
    student_id = data.get('student_id')
    
    if not lesson_id or not homework_text or not student_id:
        await callback.answer("❌ Ошибка: данные не найдены", show_alert=True)
        await state.clear()
        return
    
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.message.edit_text("❌ Занятие не найдено")
        await state.clear()
        return
    
    old_homework = lesson.get('homework', '')
    old_photo_file_id = lesson.get('homework_photo_file_id')
    old_file_id = lesson.get('homework_file_id')
    
    # Сохраняем ДЗ со старыми вложениями
    success = await db.update_lesson_homework(lesson_id, homework_text, 'assigned', old_photo_file_id, old_file_id)
    
    if success:
        await _send_homework_notification(bot, student_id, lesson, homework_text, old_homework, old_photo_file_id, old_file_id, is_editing=True)
        await callback.message.edit_text(
            f"✅ Домашнее задание сохранено:\n\n{homework_text}",
            reply_markup=kb.homework_navigation_keyboard(student_id)
        )
    else:
        await callback.message.edit_text("❌ Ошибка сохранения домашнего задания")
    
    await callback.answer()
    await state.clear()

@router.callback_query(F.data == "homework_replace_photo")
async def handle_homework_replace_photo(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора: заменить фото"""
    data = await state.get_data()
    student_id = data.get('student_id')
    
    # Устанавливаем флаг, что ожидаем фото для замены
    await state.update_data(expecting_attachment="photo", is_replacing=True)
    
    await callback.message.edit_text(
        "📷 Отправьте новое фото для домашнего задания:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"view_homework_{student_id}")]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "homework_keep_file")
async def handle_homework_keep_file(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик выбора: оставить старый файл"""
    data = await state.get_data()
    lesson_id = data.get('lesson_id')
    homework_text = data.get('homework_text')
    student_id = data.get('student_id')
    
    if not lesson_id or not homework_text or not student_id:
        await callback.answer("❌ Ошибка: данные не найдены", show_alert=True)
        await state.clear()
        return
    
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.message.edit_text("❌ Занятие не найдено")
        await state.clear()
        return
    
    old_homework = lesson.get('homework', '')
    old_photo_file_id = lesson.get('homework_photo_file_id')
    old_file_id = lesson.get('homework_file_id')
    
    # Сохраняем ДЗ со старыми вложениями
    success = await db.update_lesson_homework(lesson_id, homework_text, 'assigned', old_photo_file_id, old_file_id)
    
    if success:
        await _send_homework_notification(bot, student_id, lesson, homework_text, old_homework, old_photo_file_id, old_file_id, is_editing=True)
        await callback.message.edit_text(
            f"✅ Домашнее задание сохранено:\n\n{homework_text}",
            reply_markup=kb.homework_navigation_keyboard(student_id)
        )
    else:
        await callback.message.edit_text("❌ Ошибка сохранения домашнего задания")
    
    await callback.answer()
    await state.clear()

@router.callback_query(F.data == "homework_replace_file")
async def handle_homework_replace_file(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора: заменить файл"""
    data = await state.get_data()
    student_id = data.get('student_id')
    
    # Устанавливаем флаг, что ожидаем файл для замены
    await state.update_data(expecting_attachment="file", is_replacing=True)
    
    await callback.message.edit_text(
        "📎 Отправьте новый файл для домашнего задания:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"view_homework_{student_id}")]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "homework_remove_file")
async def handle_homework_remove_file(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик выбора: удалить файл"""
    data = await state.get_data()
    lesson_id = data.get('lesson_id')
    homework_text = data.get('homework_text')
    student_id = data.get('student_id')
    
    if not lesson_id or not homework_text or not student_id:
        await callback.answer("❌ Ошибка: данные не найдены", show_alert=True)
        await state.clear()
        return
    
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.message.edit_text("❌ Занятие не найдено")
        await state.clear()
        return
    
    old_homework = lesson.get('homework', '')
    old_photo_file_id = lesson.get('homework_photo_file_id')
    
    # Сохраняем ДЗ без файла (удаляем файл, но сохраняем фото если есть)
    success = await db.update_lesson_homework(lesson_id, homework_text, 'assigned', old_photo_file_id, '')
    
    if success:
        await _send_homework_notification(bot, student_id, lesson, homework_text, old_homework, old_photo_file_id, None, is_editing=True)
        await callback.message.edit_text(
            f"✅ Домашнее задание сохранено (файл удален):\n\n{homework_text}",
            reply_markup=kb.homework_navigation_keyboard(student_id)
        )
    else:
        await callback.message.edit_text("❌ Ошибка сохранения домашнего задания")
    
    await callback.answer()
    await state.clear()

@router.callback_query(F.data == "homework_save_no_changes")
async def handle_homework_save_no_changes(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик выбора: сохранить без изменений вложений"""
    data = await state.get_data()
    lesson_id = data.get('lesson_id')
    homework_text = data.get('homework_text')
    student_id = data.get('student_id')
    
    if not lesson_id or not homework_text or not student_id:
        await callback.answer("❌ Ошибка: данные не найдены", show_alert=True)
        await state.clear()
        return
    
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.message.edit_text("❌ Занятие не найдено")
        await state.clear()
        return
    
    old_homework = lesson.get('homework', '')
    old_photo_file_id = lesson.get('homework_photo_file_id')
    old_file_id = lesson.get('homework_file_id')
    
    # Сохраняем только текст, вложения не трогаем (передаем None)
    success = await db.update_lesson_homework(lesson_id, homework_text, 'assigned', None, None)
    
    if success:
        # Если текст изменился, отправляем уведомление
        if old_homework != homework_text:
            await _send_homework_notification(bot, student_id, lesson, homework_text, old_homework, old_photo_file_id, old_file_id, is_editing=True)
        
        await callback.message.edit_text(
            f"✅ Домашнее задание сохранено:\n\n{homework_text}",
            reply_markup=kb.homework_navigation_keyboard(student_id)
        )
    else:
        await callback.message.edit_text("❌ Ошибка сохранения домашнего задания")
    
    await callback.answer()
    await state.clear()

@router.callback_query(F.data == "homework_remove_photo")
async def handle_homework_remove_photo(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик выбора: удалить фото"""
    data = await state.get_data()
    lesson_id = data.get('lesson_id')
    homework_text = data.get('homework_text')
    student_id = data.get('student_id')
    
    if not lesson_id or not homework_text or not student_id:
        await callback.answer("❌ Ошибка: данные не найдены", show_alert=True)
        await state.clear()
        return
    
    # Получаем информацию о занятии
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.message.edit_text("❌ Занятие не найдено")
        await state.clear()
        return
    
    old_homework = lesson.get('homework', '')
    
    # Сохраняем ДЗ без фото (обратная совместимость - не передаем homework_file_id)
    success = await db.update_lesson_homework(lesson_id, homework_text, 'assigned', None, None)
    
    if success:
        # Отправляем уведомление ученику без фото
        student = await db.get_student(student_id)
        date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)
        
        notification_text = (
            f"📝 <b>Изменение домашнего задания</b>\n\n"
            f"📅 Дата занятия: {date_str} в {lesson['lesson_time']}\n\n"
        )
        if old_homework:
            notification_text += f"📖 <b>Было:</b>\n{old_homework}\n\n"
        notification_text += f"📖 <b>Стало:</b>\n{homework_text}"
        
        try:
            await bot.send_message(
                chat_id=student_id,
                text=notification_text,
                parse_mode="HTML"
            )
            logger.info(f" Отправлено уведомление ученику {student['name']} об изменении домашнего задания")
        except Exception as e:
            logger.warning(f" Не удалось отправить уведомление ученику {student_id}: {e}")
        
        await callback.message.edit_text(
            f"✅ Домашнее задание сохранено (фото удалено):\n\n{homework_text}",
            reply_markup=kb.homework_navigation_keyboard(student_id)
        )
    else:
        await callback.message.edit_text("❌ Ошибка сохранения домашнего задания")
    
    await callback.answer()
    await state.clear()

@router.callback_query(F.data == "homework_skip_second_attachment")
async def handle_homework_skip_second_attachment(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик пропуска второго вложения (когда выбрано 'оба', но пропустили второе)"""
    data = await state.get_data()
    lesson_id = data.get('lesson_id')
    source_lesson_id = data.get('source_lesson_id', lesson_id)
    homework_text = data.get('homework_text')
    student_id = data.get('student_id')
    source_student_id = data.get('source_student_id', student_id)
    saved_photo_file_id = data.get('saved_photo_file_id')
    saved_file_id = data.get('saved_file_id')
    attachment_order = data.get('attachment_order')
    
    if not lesson_id or not homework_text:
        await callback.answer("❌ Ошибка: данные не найдены", show_alert=True)
        await state.clear()
        return
    
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.message.edit_text("❌ Занятие не найдено")
        await state.clear()
        return
    
    if not student_id:
        student_id = lesson['student_id']
    if not source_student_id:
        source_student_id = lesson['student_id']
    
    old_homework = lesson.get('homework', '')
    is_editing = bool(old_homework)
    
    # Сохраняем только то, что было прикреплено первым
    if attachment_order == "photo":
        # Было фото, файл пропустили - сохраняем только фото
        success = await db.update_lesson_homework(lesson_id, homework_text, 'assigned', saved_photo_file_id, None)
        photo_file_id = saved_photo_file_id
        file_id = None
    else:
        # Был файл, фото пропустили - сохраняем только файл
        success = await db.update_lesson_homework(lesson_id, homework_text, 'assigned', None, saved_file_id)
        photo_file_id = None
        file_id = saved_file_id
    
    if success:
        await _send_homework_notification(bot, student_id, lesson, homework_text, old_homework, photo_file_id, file_id, is_editing)
        attachment_text = "с фото" if photo_file_id else "с файлом"
        
        # Проверяем, откуда был вызван обработчик
        data = await state.get_data()
        is_from_history = data.get('is_from_history', False)
        from_homework_list = data.get('from_homework_list', False)

        if is_editing or from_homework_list:
            # Если редактирование или из списка ДЗ - возвращаемся к списку ДЗ
            await callback.message.edit_text(
                f"✅ Домашнее задание сохранено {attachment_text}:\n\n{homework_text}",
                reply_markup=kb.homework_navigation_keyboard(student_id)
            )
        else:
            if is_from_history:
                # Возвращаемся к экрану истории занятий
                await update_lesson_payment_message(callback, source_lesson_id)
            else:
                await callback.message.edit_text(
                    f"✅ Домашнее задание сохранено {attachment_text}:\n\n{homework_text}",
                    reply_markup=kb.lesson_ending_keyboard(source_lesson_id, source_student_id)
                )
    else:
        await callback.message.edit_text("❌ Ошибка сохранения домашнего задания")
    
    await callback.answer()
    await state.clear()

@router.callback_query(F.data == "homework_add_photo_no")
async def handle_homework_add_photo_no(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик выбора: не прикреплять вложения - сохранить ДЗ"""
    data = await state.get_data()
    lesson_id = data.get('lesson_id')
    source_lesson_id = data.get('source_lesson_id', lesson_id)
    homework_text = data.get('homework_text')
    student_id = data.get('student_id')
    source_student_id = data.get('source_student_id', student_id)
    
    if not lesson_id or not homework_text:
        await callback.answer("❌ Ошибка: данные не найдены", show_alert=True)
        await state.clear()
        return
    
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.message.edit_text("❌ Занятие не найдено")
        await state.clear()
        return
    
    old_homework = lesson.get('homework', '')
    is_editing = bool(old_homework)
    
    if not student_id:
        student_id = lesson['student_id']
    if not source_student_id:
        source_student_id = lesson['student_id']
    
    # Сохраняем ДЗ без вложений (или удаляем существующие при редактировании)
    success = await db.update_lesson_homework(lesson_id, homework_text, 'assigned', None, None)
    
    if success:
        await _send_homework_notification(bot, student_id, lesson, homework_text, old_homework, None, None, is_editing)

        # Проверяем, откуда был вызван обработчик
        is_from_history = data.get('is_from_history', False)
        from_homework_list = data.get('from_homework_list', False)

        if is_editing or from_homework_list:
            # Если редактирование или из списка ДЗ - возвращаемся к списку ДЗ
            await callback.message.edit_text(
                f"✅ Домашнее задание сохранено:\n\n{homework_text}",
                reply_markup=kb.homework_navigation_keyboard(student_id)
            )
        else:
            target_date = format_date_with_weekday(lesson['lesson_date'], full_format=True)
            if is_from_history:
                # Возвращаемся к экрану истории занятий
                await update_lesson_payment_message(callback, source_lesson_id)
            else:
                # Возвращаемся к уведомлению об окончании
                await callback.message.edit_text(
                    f"✅ Домашнее задание добавлено для занятия:\n"
                    f"📅 {target_date} в {lesson['lesson_time']}\n\n"
                    f"{homework_text}",
                    reply_markup=kb.lesson_ending_keyboard(source_lesson_id, source_student_id),
                    parse_mode="HTML"
                )
    else:
        await callback.message.edit_text("❌ Ошибка сохранения домашнего задания")
    
    await callback.answer()
    await state.clear()

@router.message(AdminPanelStates.adding_homework_photo, F.photo)
async def process_homework_photo(message: Message, state: FSMContext, bot: Bot):
    """Обработать фото для домашнего задания"""
    data = await state.get_data()
    lesson_id = data.get('lesson_id')
    source_lesson_id = data.get('source_lesson_id', lesson_id)
    homework_text = data.get('homework_text')
    student_id = data.get('student_id')
    source_student_id = data.get('source_student_id', student_id)
    expecting_attachment = data.get('expecting_attachment', 'photo')
    attachment_order = data.get('attachment_order')
    saved_photo_file_id = data.get('saved_photo_file_id')
    saved_file_id = data.get('saved_file_id')
    
    if not lesson_id or not homework_text:
        await message.answer("❌ Ошибка: данные не найдены")
        await state.clear()
        return
    
    # Получаем file_id самого большого размера фото
    photo = message.photo[-1]
    photo_file_id = photo.file_id
    
    # Получаем информацию о занятии
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await message.answer("❌ Занятие не найдено")
        await state.clear()
        return
    
    if not student_id:
        student_id = lesson['student_id']
    if not source_student_id:
        source_student_id = lesson['student_id']
    
    # Определяем, это редактирование или добавление нового ДЗ
    old_homework = lesson.get('homework', '')
    is_editing = bool(old_homework)
    
    # Проверяем, это замена при редактировании или добавление нового
    is_replacing = data.get('is_replacing', False)
    
    # Логика в зависимости от типа ожидаемого вложения
    if expecting_attachment == "photo":
        # Только фото - сохраняем и завершаем
        if is_replacing:
            # При замене сохраняем старое файл если есть
            old_file_id = lesson.get('homework_file_id')
            success = await db.update_lesson_homework(lesson_id, homework_text, 'assigned', photo_file_id, old_file_id)
        else:
            # При добавлении нового
            success = await db.update_lesson_homework(lesson_id, homework_text, 'assigned', photo_file_id, None)
        
        if success:
            old_file_id_for_notification = lesson.get('homework_file_id') if is_replacing else None
            await _send_homework_notification(bot, student_id, lesson, homework_text, old_homework, photo_file_id, old_file_id_for_notification, is_editing)

            # Проверяем, откуда был вызван обработчик
            from_homework_list = data.get('from_homework_list', False)

            # Если редактирование или из списка ДЗ - возвращаемся к списку ДЗ
            if is_editing or from_homework_list:
                reply_markup = kb.homework_navigation_keyboard(student_id)
            else:
                reply_markup = kb.lesson_ending_keyboard(source_lesson_id, source_student_id)

            await message.answer(
                f"✅ Домашнее задание сохранено с фото:\n\n{homework_text}",
                reply_markup=reply_markup
            )
        else:
            await message.answer("❌ Ошибка сохранения домашнего задания")
        await state.clear()
    
    elif expecting_attachment == "both":
        # Оба вложения - сохраняем фото во временное хранилище и запрашиваем файл
        if attachment_order == "photo":
            # Сначала фото, потом файл - сохраняем фото, запрашиваем файл
            await state.update_data(saved_photo_file_id=photo_file_id)
            await message.answer(
                "✅ Фото сохранено!\n\n📎 Теперь отправьте файл для домашнего задания:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Пропустить файл", callback_data="homework_skip_second_attachment")],
                    [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"lesson_ending_{source_lesson_id}")]
                ])
            )
        else:
            # Сначала файл, потом фото - файл уже сохранен, сохраняем фото и завершаем
            file_id = saved_file_id
            success = await db.update_lesson_homework(lesson_id, homework_text, 'assigned', photo_file_id, file_id)
            if success:
                await _send_homework_notification(bot, student_id, lesson, homework_text, old_homework, photo_file_id, file_id, is_editing)

                # Проверяем, откуда был вызван обработчик
                from_homework_list = data.get('from_homework_list', False)

                # Если редактирование или из списка ДЗ - возвращаемся к списку ДЗ
                if is_editing or from_homework_list:
                    reply_markup = kb.homework_navigation_keyboard(student_id)
                else:
                    reply_markup = kb.lesson_ending_keyboard(source_lesson_id, source_student_id)

                await message.answer(
                    f"✅ Домашнее задание сохранено с фото и файлом:\n\n{homework_text}",
                    reply_markup=reply_markup
                )
            else:
                await message.answer("❌ Ошибка сохранения домашнего задания")
            await state.clear()
    else:
        await message.answer("❌ Неожиданная ошибка")
        await state.clear()

@router.message(AdminPanelStates.adding_homework_photo, F.document)
async def process_homework_document(message: Message, state: FSMContext, bot: Bot):
    """Обработать файл для домашнего задания"""
    data = await state.get_data()
    lesson_id = data.get('lesson_id')
    source_lesson_id = data.get('source_lesson_id', lesson_id)
    homework_text = data.get('homework_text')
    student_id = data.get('student_id')
    source_student_id = data.get('source_student_id', student_id)
    expecting_attachment = data.get('expecting_attachment', 'file')
    attachment_order = data.get('attachment_order')
    saved_photo_file_id = data.get('saved_photo_file_id')
    saved_file_id = data.get('saved_file_id')
    
    if not lesson_id or not homework_text:
        await message.answer("❌ Ошибка: данные не найдены")
        await state.clear()
        return
    
    # Получаем file_id файла
    document = message.document
    file_id = document.file_id
    
    # Получаем информацию о занятии
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await message.answer("❌ Занятие не найдено")
        await state.clear()
        return
    
    if not student_id:
        student_id = lesson['student_id']
    if not source_student_id:
        source_student_id = lesson['student_id']
    
    # Определяем, это редактирование или добавление нового ДЗ
    old_homework = lesson.get('homework', '')
    is_editing = bool(old_homework)
    
    # Проверяем, это замена при редактировании или добавление нового
    is_replacing = data.get('is_replacing', False)
    
    # Логика в зависимости от типа ожидаемого вложения
    if expecting_attachment == "file":
        # Только файл - сохраняем и завершаем
        if is_replacing:
            # При замене сохраняем старое фото если есть
            old_photo_file_id = lesson.get('homework_photo_file_id')
            success = await db.update_lesson_homework(lesson_id, homework_text, 'assigned', old_photo_file_id, file_id)
        else:
            # При добавлении нового
            success = await db.update_lesson_homework(lesson_id, homework_text, 'assigned', None, file_id)
        
        if success:
            old_photo_file_id_for_notification = lesson.get('homework_photo_file_id') if is_replacing else None
            await _send_homework_notification(bot, student_id, lesson, homework_text, old_homework, old_photo_file_id_for_notification, file_id, is_editing)

            # Проверяем, откуда был вызван обработчик
            from_homework_list = data.get('from_homework_list', False)

            # Если редактирование или из списка ДЗ - возвращаемся к списку ДЗ
            if is_editing or from_homework_list:
                reply_markup = kb.homework_navigation_keyboard(student_id)
            else:
                reply_markup = kb.lesson_ending_keyboard(source_lesson_id, source_student_id)

            await message.answer(
                f"✅ Домашнее задание сохранено с файлом:\n\n{homework_text}",
                reply_markup=reply_markup
            )
        else:
            await message.answer("❌ Ошибка сохранения домашнего задания")
        await state.clear()
    
    elif expecting_attachment == "both":
        # Оба вложения - сохраняем файл во временное хранилище и запрашиваем фото
        if attachment_order == "file":
            # Сначала файл, потом фото - сохраняем файл, запрашиваем фото
            await state.update_data(saved_file_id=file_id)
            await message.answer(
                "✅ Файл сохранен!\n\n📷 Теперь отправьте фото для домашнего задания:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Пропустить фото", callback_data="homework_skip_second_attachment")],
                    [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"lesson_ending_{source_lesson_id}")]
                ])
            )
        else:
            # Сначала фото, потом файл - фото уже сохранено, сохраняем файл и завершаем
            photo_file_id = saved_photo_file_id
            success = await db.update_lesson_homework(lesson_id, homework_text, 'assigned', photo_file_id, file_id)
            if success:
                await _send_homework_notification(bot, student_id, lesson, homework_text, old_homework, photo_file_id, file_id, is_editing)

                # Проверяем, откуда был вызван обработчик
                from_homework_list = data.get('from_homework_list', False)

                # Если редактирование или из списка ДЗ - возвращаемся к списку ДЗ
                if is_editing or from_homework_list:
                    reply_markup = kb.homework_navigation_keyboard(student_id)
                else:
                    reply_markup = kb.lesson_ending_keyboard(source_lesson_id, source_student_id)

                await message.answer(
                    f"✅ Домашнее задание сохранено с фото и файлом:\n\n{homework_text}",
                    reply_markup=reply_markup
                )
            else:
                await message.answer("❌ Ошибка сохранения домашнего задания")
            await state.clear()
    else:
        await message.answer("❌ Неожиданная ошибка")
        await state.clear()

@router.message(AdminPanelStates.adding_homework_photo)
async def process_homework_photo_invalid(message: Message, state: FSMContext):
    """Обработчик, если в состоянии ожидания вложения пришло не фото и не файл"""
    data = await state.get_data()
    expecting_attachment = data.get('expecting_attachment', 'photo')
    
    if expecting_attachment == "photo":
        text = "❌ Пожалуйста, отправьте фото или нажмите 'Пропустить'"
    elif expecting_attachment == "file":
        text = "❌ Пожалуйста, отправьте файл или нажмите 'Пропустить'"
    else:
        text = "❌ Пожалуйста, отправьте фото или файл"
    
    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Пропустить", callback_data="homework_add_photo_no")]
        ])
    )

@router.callback_query(F.data.startswith("confirm_attendance_"))
async def handle_confirm_attendance(callback: CallbackQuery):
    """Обработчик подтверждения участия в занятии"""
    try:
        lesson_id = int(callback.data.split("_")[-1])
        
        # Получаем информацию о занятии
        lesson = await db.get_lesson_by_id(lesson_id)
        if not lesson:
            await callback.answer("❌ Занятие не найдено", show_alert=True)
            return
        
        # Проверяем, не подтверждено ли уже
        if lesson.get('confirmation_status') == 'confirmed':
            await callback.answer("✅ Вы уже подтвердили участие", show_alert=True)
            return
        
        # Обновляем статус подтверждения
        await db.update_lesson_confirmation(lesson_id, 'confirmed')
        
        # Отправляем подтверждение ученику
        await callback.answer("✅ Спасибо! Ваше участие подтверждено", show_alert=True)
        
        # Обновляем сообщение, убирая кнопку
        try:
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ Вы подтвердили участие",
                reply_markup=None
            )
        except:
            # Если не удалось отредактировать, просто отправляем новое сообщение
            pass
        
        # Отправляем уведомление учителю о подтверждении участия
        student = await db.get_student(lesson['student_id'])
        date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)
        teacher_message = (
            f"✅ Подтверждение участия\n\n"
            f"👤 Ученик: {student['name']}\n"
            f"📅 {date_str} в {lesson['lesson_time']}\n"
            f"📍 Формат: {'онлайн' if lesson['lesson_format'] == 'online' else 'оффлайн'}"
        )

        try:
            await callback.bot.send_message(
                chat_id=TUTOR_ID,
                text=teacher_message
            )
            logger.info(f" Отправлено уведомление учителю о подтверждении участия учеником {student['name']}")
        except Exception as e:
            logger.warning(f" Не удалось отправить уведомление учителю: {e}")
            
    except Exception as e:
        logger.error(f" Ошибка обработки подтверждения участия: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.callback_query(F.data.startswith("lesson_complete_"))
async def handle_lesson_complete(callback: CallbackQuery, bot: Bot):
    """Отметить занятие как завершенное"""
    if not await check_admin_access_callback(callback):
        return
        
    lesson_id = int(callback.data.split("_")[-1])
    
    # Получаем информацию о занятии перед завершением
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.answer("❌ Занятие не найдено", show_alert=True)
        return
    
    # Отменяем все оставшиеся задачи для занятия
    try:
        from bot_template.database.task_manager import TaskManager
        task_manager = TaskManager(db)
        await task_manager.cancel_lesson_tasks(lesson_id)
    except Exception as task_error:
        logger.warning(f" Ошибка отмены задач для занятия #{lesson_id}: {task_error}")
    
    success = await db.complete_lesson(lesson_id)
    
    if success:
        # Отправляем уведомление ученику
        student_id = lesson['student_id']
        student = await db.get_student(student_id)
        date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)
        
        duration_hours = lesson['duration'] // 60
        duration_mins = lesson['duration'] % 60
        if duration_mins:
            duration_str = f"{duration_hours}ч {duration_mins}мин"
        else:
            duration_str = f"{duration_hours}ч"
        
        notification_text = (
            f"✅ <b>Занятие завершено</b>\n\n"
            f"📅 {date_str} в {lesson['lesson_time']}\n"
            f"⏱️ Продолжительность: {duration_str}\n"
        )
        
        # Добавляем домашнее задание, если задано
        if lesson.get('homework'):
            notification_text += f"\n📝 <b>Домашнее задание:</b>\n{lesson['homework']}"
        
        try:
            await bot.send_message(
                chat_id=student_id,
                text=notification_text,
                parse_mode="HTML"
            )
            logger.info(f" Отправлено уведомление ученику {student['name']} о завершении занятия")
        except Exception as e:
            logger.warning(f" Не удалось отправить уведомление ученику {student_id}: {e}")
        
        await callback.answer("✅ Занятие завершено!", show_alert=True)
        # Не редактируем исходное сообщение, чтобы оно оставалось с информацией об уроке
    else:
        await callback.answer("❌ Ошибка завершения занятия", show_alert=True)

@router.callback_query(F.data.startswith("lesson_ending_"))
async def back_to_lesson_ending(callback: CallbackQuery, state: FSMContext):
    """Вернуться к меню завершения занятия"""
    if not await check_admin_access_callback(callback):
        return
        
    lesson_id = int(callback.data.split("_")[-1])
    await state.clear()

    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.answer("❌ Занятие не найдено", show_alert=True)
        return
    
    # Обновляем только клавиатуру, не трогая текст сообщения
    await callback.message.edit_reply_markup(
        reply_markup=kb.lesson_ending_keyboard(lesson_id, lesson['student_id'])
    )
    await callback.answer()

# === ИНТЕРФЕЙС "МОИ ЗАНЯТИЯ" ДЛЯ УЧЕНИКОВ ===

@router.message(F.text == '📚 Мои занятия')
async def my_lessons_menu(message: Message):
    """Главное меню 'Мои занятия' для ученика"""
    user_id = message.from_user.id
    
    # Проверяем, зарегистрирован ли ученик
    student = await db.get_student(user_id)
    if not student:
        await message.answer(
            "❌ Вы не зарегистрированы в системе.\n\n"
            "Пожалуйста, пройдите регистрацию, нажав /start"
        )
        return
    
    await message.answer(
        "📚 МОИ ЗАНЯТИЯ\n\n"
        "Выберите, что хотите посмотреть:",
        reply_markup=kb.my_lessons_keyboard()
    )

@router.callback_query(F.data == "my_lessons_upcoming")
async def show_upcoming_lessons(callback: CallbackQuery):
    """Показать предстоящие занятия ученика (на неделю вперед)"""
    user_id = callback.from_user.id
    
    # Получаем все занятия ученика
    lessons = await db.get_lessons_by_student(user_id)
    
    # Фильтруем только предстоящие (scheduled и дата от сегодня до +7 дней)
    today = get_local_time().date()
    week_later = today + timedelta(days=7)
    upcoming = [
        l for l in lessons 
        if l['status'] == 'scheduled' and 
        today <= datetime.strptime(l['lesson_date'], '%Y-%m-%d').date() <= week_later
    ]
    
    if not upcoming:
        await callback.message.edit_text(
            "📅 У вас нет предстоящих занятий на ближайшую неделю",
            reply_markup=kb.back_to_lessons_keyboard()
        )
        await callback.answer()
        return
    
    # Сортируем по дате
    upcoming.sort(key=lambda x: (x['lesson_date'], x['lesson_time']))
    
    # Формируем сообщение (компактно для мобильных)
    message_text = "🔮 Предстоящие (неделя)\n"
    
    for lesson in upcoming[:10]:  # Показываем максимум 10
        date_str = format_date_with_weekday(lesson['lesson_date'])
        time_str = format_lesson_time(lesson['lesson_time'], lesson.get('duration', 60))
        hw_emoji = "✅" if lesson.get('homework_status') == 'completed' else "📖" if lesson.get('homework') else ""
        hw_text = f" {hw_emoji}ДЗ" if hw_emoji else ""
        message_text += f"⏳ {date_str} {time_str}, {lesson['price']:.0f}₽{hw_text}\n"
    
    if len(upcoming) > 10:
        message_text += f"... еще {len(upcoming) - 10}"
    
    await callback.message.edit_text(
        message_text,
        reply_markup=kb.back_to_lessons_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "my_lessons_history")
async def show_lessons_history(callback: CallbackQuery):
    """Показать историю занятий ученика с умным фильтром (неделя назад + неделя вперед + неоплаченные)"""
    user_id = callback.from_user.id
    
    # Получаем занятия с умным фильтром
    lessons_data = await db.get_lessons_smart_filter(user_id)
    
    unpaid = lessons_data['unpaid']
    upcoming = lessons_data['upcoming']
    past = lessons_data['past']
    
    # Проверяем, есть ли вообще занятия
    if not unpaid and not upcoming and not past:
        await callback.message.edit_text(
            "📅 Нет занятий для отображения\n\n"
            "🔍 Показываются:\n"
            "• Неоплаченные занятия\n"
            "• Предстоящие на неделю\n"
            "• Прошедшие за неделю",
            reply_markup=kb.back_to_lessons_keyboard()
        )
        await callback.answer()
        return
    
    # Формируем сообщение с разделением на секции
    message_text = "📚 <b>МОИ ЗАНЯТИЯ</b>\n\n"
    
    # Секция: Неоплаченные
    if unpaid:
        debt = sum(l['price'] for l in unpaid)
        message_text += f"⚠️ <b>Неоплаченные</b> (Долг: {debt:.0f}₽)\n"
        
        for lesson in unpaid[:10]:
            date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)
            time_str = format_lesson_time(lesson['lesson_time'], lesson.get('duration', 60))
            hw_text = " 📖ДЗ" if lesson.get('homework') else ""
            message_text += f"❌ {date_str} {time_str} | {lesson['price']:.0f}₽{hw_text}\n"
        
        if len(unpaid) > 10:
            message_text += f"... еще {len(unpaid) - 10}\n"
        message_text += "\n"
    
    # Секция: Предстоящие (компактно для мобильных)
    if upcoming:
        message_text += "🔮 Предстоящие (неделя)\n"
        
        for lesson in upcoming[:10]:
            date_str = format_date_with_weekday(lesson['lesson_date'])
            time_str = format_lesson_time(lesson['lesson_time'], lesson.get('duration', 60))
            hw_emoji = "✅" if lesson.get('homework_status') == 'completed' else "📖" if lesson.get('homework') else ""
            hw_text = f" {hw_emoji}ДЗ" if hw_emoji else ""
            message_text += f"⏳ {date_str} {time_str}, {lesson['price']:.0f}₽{hw_text}\n"
        
        if len(upcoming) > 10:
            message_text += f"... еще {len(upcoming) - 10}\n"
        message_text += "\n"
    
    # Секция: Прошедшие (компактно для мобильных)
    if past:
        message_text += "✅ <b>Прошедшие</b> (неделя)\n"
        
        for lesson in past[:10]:
            date_str = format_date_with_weekday(lesson['lesson_date'])
            time_str = format_lesson_time(lesson['lesson_time'], lesson.get('duration', 60))
            hw_status = ""
            if lesson.get('homework'):
                hw_status = " ✅ДЗ" if lesson.get('homework_status') == 'completed' else " 📖ДЗ"
            message_text += f"✅ {date_str} {time_str} | {lesson['price']:.0f}₽{hw_status}\n"
        
        if len(past) > 10:
            message_text += f"... еще {len(past) - 10}\n"
        message_text += "\n"
    
    await callback.message.edit_text(
        message_text,
        reply_markup=kb.back_to_lessons_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_my_lessons")
async def back_to_my_lessons(callback: CallbackQuery):
    """Вернуться к меню 'Мои занятия'"""
    await callback.message.edit_text(
        "📚 МОИ ЗАНЯТИЯ\n\n"
        "Выберите, что хотите посмотреть:",
        reply_markup=kb.my_lessons_keyboard()
    )
    await callback.answer()

@router.message(F.text == '📖 ДЗ')
async def show_my_homework(message: Message):
    """Показать краткую информацию о домашних заданиях ученика"""
    user_id = message.from_user.id
    
    # Проверяем, зарегистрирован ли ученик
    student = await db.get_student(user_id)
    if not student:
        await message.answer(
            "❌ Вы не зарегистрированы в системе.\n\n"
            "Пожалуйста, пройдите регистрацию, нажав /start"
        )
        return
    
    try:
        # Получаем ДЗ с умным фильтром (прошлая и следующая неделя)
        homework_data = await db.get_student_homework_smart(user_id)
        past_week = homework_data.get('active', [])  # Прошлая неделя
        next_week = homework_data.get('recent', [])    # Следующая неделя
        
        # Объединяем занятия прошлой и следующей недели
        all_lessons = past_week + next_week
        
        # Формируем текст сообщения с краткой информацией
        message_text = "📖 <b>МОИ ДОМАШНИЕ ЗАДАНИЯ</b>\n\n"
        
        if not all_lessons:
            message_text += "📭 Нет занятий за прошлую и следующую неделю"
        else:
            # Прошлая неделя
            if past_week:
                message_text += "📅 <b>Прошлая неделя:</b>\n"
                for lesson in past_week:
                    date_str = format_date_with_weekday(lesson['lesson_date'], full_format=False)
                    has_homework = bool(lesson.get('homework') and lesson.get('homework').strip())
                    homework_status = "📝 ДЗ есть" if has_homework else "❌ ДЗ нет"
                    message_text += f"• {date_str} - {homework_status}\n"
                message_text += "\n"
            
            # Следующая неделя
            if next_week:
                message_text += "🔮 <b>Следующая неделя:</b>\n"
                for lesson in next_week:
                    date_str = format_date_with_weekday(lesson['lesson_date'], full_format=False)
                    has_homework = bool(lesson.get('homework') and lesson.get('homework').strip())
                    homework_status = "📝 ДЗ есть" if has_homework else "❌ ДЗ нет"
                    message_text += f"• {date_str} - {homework_status}\n"
        
        # Клавиатура со списком занятий
        keyboard = kb.student_homework_list_keyboard(all_lessons)
        
        await message.answer(
            message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в show_my_homework: {error_details}")
        await message.answer(
            "❌ Произошла ошибка при загрузке домашних заданий",
            reply_markup=kb.main
        )

@router.callback_query(F.data.startswith("student_homework_detail_"))
async def show_student_homework_detail(callback: CallbackQuery, bot: Bot):
    """Показать детальную информацию о домашнем задании для ученика"""
    try:
        lesson_id = int(callback.data.split("_")[-1])
        user_id = callback.from_user.id
        
        # Получаем занятие
        lesson = await db.get_lesson_by_id(lesson_id)
        if not lesson:
            await callback.answer("❌ Занятие не найдено", show_alert=True)
            return
        
        # Проверяем, что это занятие ученика
        if lesson['student_id'] != user_id:
            await callback.answer("❌ Нет доступа", show_alert=True)
            return
        
        # Формируем информацию о занятии
        date_str = format_date_with_weekday(lesson['lesson_date'], full_format=False)
        duration = lesson.get('duration', 60)
        
        # Форматируем время в формате XX:XX - XX:XX
        try:
            start_dt = datetime.strptime(lesson['lesson_time'], '%H:%M')
            end_dt = start_dt + timedelta(minutes=duration)
            end_time = end_dt.strftime('%H:%M')
            time_str = f"{lesson['lesson_time']} - {end_time}"
        except:
            time_str = lesson['lesson_time']
        
        # Формируем текст сообщения
        message_text = f"📖 <b>Домашнее задание</b>\n\n"
        message_text += f"📅 {date_str}\n"
        message_text += f"🕐 {time_str}\n"
        
        # Добавляем текст ДЗ, если есть
        homework_text = (lesson.get('homework') or '').strip()
        if homework_text:
            message_text += f"\n📝 <b>Задание:</b>\n{homework_text}"
        else:
            message_text += f"\n❌ Домашнее задание не задано"
        
        # Получаем file_id фото и файла, если есть
        photo_file_id = lesson.get('homework_photo_file_id')
        file_id = lesson.get('homework_file_id')
        
        # Клавиатура возврата
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад к списку ДЗ", callback_data="back_to_homework_list")]
        ])
        
        # Вариант C: фото с текстом, файл с коротким пояснением
        try:
            await callback.message.delete()
            
            # Если есть фото - отправляем фото с текстом
            if photo_file_id:
                await bot.send_photo(
                    chat_id=user_id,
                    photo=photo_file_id,
                    caption=message_text,
                    reply_markup=keyboard if not file_id else None,  # Клавиатуру только если нет файла
                    parse_mode="HTML"
                )
            else:
                # Если нет фото - отправляем текст
                await bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    reply_markup=keyboard if not file_id else None,  # Клавиатуру только если нет файла
                    parse_mode="HTML"
                )
            
            # Если есть файл - отправляем файл с коротким пояснением
            if file_id:
                await bot.send_document(
                    chat_id=user_id,
                    document=file_id,
                    caption="📎 Файл к домашнему заданию",
                    reply_markup=keyboard
                )
        except Exception as e:
            # Если не удалось отправить, отправляем текст
            logger.warning(f" Не удалось отправить вложения: {e}")
            await callback.message.edit_text(
                message_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        
        await callback.answer()
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в show_student_homework_detail: {error_details}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.callback_query(F.data == "back_to_homework_list")
async def back_to_homework_list(callback: CallbackQuery, bot: Bot):
    """Вернуться к списку домашних заданий"""
    user_id = callback.from_user.id
    
    # Проверяем, зарегистрирован ли ученик
    student = await db.get_student(user_id)
    if not student:
        await callback.answer("❌ Вы не зарегистрированы", show_alert=True)
        return
    
    try:
        # Получаем ДЗ с умным фильтром
        homework_data = await db.get_student_homework_smart(user_id)
        past_week = homework_data.get('active', [])
        next_week = homework_data.get('recent', [])
        
        all_lessons = past_week + next_week
        
        # Формируем текст сообщения с краткой информацией
        message_text = "📖 <b>МОИ ДОМАШНИЕ ЗАДАНИЯ</b>\n\n"
        
        if not all_lessons:
            message_text += "📭 Нет занятий за прошлую и следующую неделю"
        else:
            # Прошлая неделя
            if past_week:
                message_text += "📅 <b>Прошлая неделя:</b>\n"
                for lesson in past_week:
                    date_str = format_date_with_weekday(lesson['lesson_date'], full_format=False)
                    has_homework = bool(lesson.get('homework') and lesson.get('homework').strip())
                    homework_status = "📝 ДЗ есть" if has_homework else "❌ ДЗ нет"
                    message_text += f"• {date_str} - {homework_status}\n"
                message_text += "\n"
            
            # Следующая неделя
            if next_week:
                message_text += "🔮 <b>Следующая неделя:</b>\n"
                for lesson in next_week:
                    date_str = format_date_with_weekday(lesson['lesson_date'], full_format=False)
                    has_homework = bool(lesson.get('homework') and lesson.get('homework').strip())
                    homework_status = "📝 ДЗ есть" if has_homework else "❌ ДЗ нет"
                    message_text += f"• {date_str} - {homework_status}\n"
        
        # Клавиатура со списком занятий
        keyboard = kb.student_homework_list_keyboard(all_lessons)
        
        # Проверяем, является ли сообщение фото
        # Если это фото, удаляем его и отправляем новое текстовое сообщение
        try:
            # Пытаемся отредактировать текст (для текстовых сообщений)
            await callback.message.edit_text(
                message_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as edit_error:
            # Если не получилось (это фото), удаляем сообщение и отправляем новое
            try:
                await callback.message.delete()
                await bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as delete_error:
                logger.warning(f" Не удалось удалить сообщение: {delete_error}")
                # Если не удалось удалить, просто отправляем новое сообщение
                await bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        
        await callback.answer()
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в back_to_homework_list: {error_details}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

# === УПРАВЛЕНИЕ ОПЛАТОЙ ЗАНЯТИЙ (ДЛЯ УЧИТЕЛЯ) ===

@router.callback_query(F.data.startswith("manage_payments_"))
async def manage_payments(callback: CallbackQuery):
    """Показать список занятий ученика для управления оплатой (с умным фильтром)"""
    if not await check_admin_access_callback(callback):
        return
    
    student_id = int(callback.data.split("_")[-1])
    
    # Получаем ученика
    student = await db.get_student(student_id)
    if not student:
        await callback.answer("❌ Ученик не найден", show_alert=True)
        return
    
    # Используем умный фильтр
    lessons_data = await db.get_lessons_smart_filter(student_id)
    
    unpaid = lessons_data['unpaid']
    upcoming = lessons_data['upcoming']
    past = lessons_data['past']
    
    all_lessons = unpaid + upcoming + past
    
    if not all_lessons:
        await callback.message.edit_text(
            f"💰 <b>Управление оплатой: {student['name']}</b>\n\n"
            "📅 Нет занятий для отображения\n\n"
            "🎯 Показываются:\n"
            "• Неоплаченные (все)\n"
            "• Предстоящие (неделя)\n"
            "• Прошедшие (неделя)",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👤 К профилю", callback_data=f"view_student_{student_id}")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    # Считаем задолженность
    debt = sum(l['price'] for l in unpaid)
    
    # Формируем сообщение
    message_text = f"💰 <b>Управление оплатой: {student['name']}</b>\n\n"
    
    if debt > 0:
        message_text += f"⚠️ Задолженность: <b>{debt:.0f}₽</b> за {len(unpaid)} занятий\n\n"
    
    message_text += "🎯 <b>Умный фильтр:</b> неоплаченные + неделя\n\n"
    
    # Создаем inline-кнопки для каждого занятия
    buttons = []
    
    # Сначала неоплаченные
    if unpaid:
        message_text += "⚠️ <b>Неоплаченные:</b>\n"
        for lesson in unpaid[:10]:
            date_str = format_date_with_weekday(lesson['lesson_date'])
            
            message_text += f"❌ {date_str} в {lesson['lesson_time']} | {lesson['price']:.0f}₽\n"
            
            button_text = f"{date_str} - {lesson['price']:.0f}₽ ❌"
            buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"edit_payment_{lesson['id']}"
            )])
        message_text += "\n"
    
    # Потом предстоящие
    if upcoming:
        message_text += "🔮 <b>Предстоящие:</b>\n"
        for lesson in upcoming[:5]:
            date_str = format_date_with_weekday(lesson['lesson_date'])
            
            message_text += f"⏳ {date_str} в {lesson['lesson_time']} | {lesson['price']:.0f}₽\n"
            
            button_text = f"{date_str} - {lesson['price']:.0f}₽"
            buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"edit_payment_{lesson['id']}"
            )])
        message_text += "\n"
    
    # И прошедшие
    if past:
        message_text += "✅ <b>Прошедшие:</b>\n"
        for lesson in past[:5]:
            date_str = format_date_with_weekday(lesson['lesson_date'])
            
            message_text += f"✅ {date_str} в {lesson['lesson_time']} | {lesson['price']:.0f}₽\n"
            
            button_text = f"{date_str} - {lesson['price']:.0f}₽ ✅"
            buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"edit_payment_{lesson['id']}"
            )])
    
    buttons.append([InlineKeyboardButton(text="👤 К профилю", callback_data=f"view_student_{student_id}")])
    
    await callback.message.edit_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()

async def update_lesson_payment_message(callback: CallbackQuery, lesson_id: int):
    """Вспомогательная функция для обновления сообщения о занятии с актуальными данными"""
    # Получаем занятие с информацией об ученике
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("""
            SELECT l.*, s.name as student_name
            FROM lessons l
            JOIN students s ON l.student_id = s.user_id
            WHERE l.id = ?
        """, (lesson_id,)) as cursor:
            lesson = await cursor.fetchone()
    
    if not lesson:
        await callback.answer("❌ Занятие не найдено", show_alert=True)
        return None
    
    lesson = dict(lesson)
    
    # Формируем информацию о занятии
    date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)
    
    status_text = {
        'scheduled': '⏳ Запланировано',
        'completed': '✅ Проведено',
        'cancelled': '❌ Отменено'
    }.get(lesson.get('status', 'scheduled'), '❓ Неизвестно')
    
    payment_text = {
        'paid': '✅ Оплачено',
        'unpaid': '❌ Не оплачено',
        'pending': '⏳ Ожидается'
    }.get(lesson.get('payment_status', 'unpaid'), '❓ Неизвестно')
    
    duration = lesson.get('duration', 60)
    duration_hours = duration // 60
    duration_mins = duration % 60
    duration_str = f"{duration_hours}ч {duration_mins}мин" if duration_mins else f"{duration_hours}ч"
    
    message_text = (
        f"📝 <b>Занятие</b>\n\n"
        f"👤 Ученик: {lesson['student_name']}\n"
        f"📅 Дата: {date_str} в {lesson['lesson_time']}\n"
        f"⏱️ Продолжительность: {duration_str}\n"
        f"💰 Стоимость: {lesson['price']:.0f}₽\n"
        f"📊 Статус: {status_text}\n"
        f"💵 Оплата: <b>{payment_text}</b>\n"
    )
    
    if lesson.get('homework'):
        message_text += f"\n📖 ДЗ: {lesson['homework']}"
    
    await callback.message.edit_text(
        message_text,
        reply_markup=kb.lesson_payment_keyboard(
            lesson_id,
            lesson['student_id'],
            lesson.get('payment_status', 'unpaid'),
            lesson.get('status', 'scheduled')
        ),
        parse_mode="HTML"
    )
    return lesson

@router.callback_query(F.data.startswith("edit_payment_"))
async def edit_payment_status(callback: CallbackQuery):
    """Изменить статус оплаты конкретного занятия"""
    if not await check_admin_access_callback(callback):
        return
        
    lesson_id = int(callback.data.split("_")[-1])
    await update_lesson_payment_message(callback, lesson_id)
    await callback.answer()

@router.callback_query(F.data.startswith("set_paid_"))
async def set_lesson_paid(callback: CallbackQuery, bot: Bot):
    """Отметить занятие как оплаченное"""
    if not await check_admin_access_callback(callback):
        return
        
    lesson_id = int(callback.data.split("_")[-1])
    
    # Получаем информацию о занятии
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.answer("❌ Занятие не найдено", show_alert=True)
        return
    
    success = await db.update_lesson_payment_status(lesson_id, 'paid')
    
    if success:
        # Отправляем уведомление ученику
        student_id = lesson['student_id']
        student = await db.get_student(student_id)
        debt_info = await db.get_student_debt(student_id)
        date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)
        
        notification_text = (
            f"💰 <b>Оплата получена</b>\n\n"
            f"📅 {date_str} в {lesson['lesson_time']}\n"
            f"💵 Сумма: {lesson['price']:.0f}₽\n"
        )
        
        # Добавляем информацию об остатке долга, если есть
        if debt_info['total_debt'] > 0:
            notification_text += (
                f"\n⚠️ <b>Остаток долга:</b> {debt_info['total_debt']:.0f}₽ "
                f"за {debt_info['unpaid_count']} занятий"
            )
        
        try:
            await bot.send_message(
                chat_id=student_id,
                text=notification_text,
                parse_mode="HTML"
            )
            logger.info(f" Отправлено уведомление ученику {student['name']} об оплате занятия")
        except Exception as e:
            logger.warning(f" Не удалось отправить уведомление ученику {student_id}: {e}")
        
        await callback.answer("✅ Занятие отмечено как оплаченное", show_alert=True)
        # Обновляем отображение с актуальными данными
        await update_lesson_payment_message(callback, lesson_id)
    else:
        await callback.answer("❌ Ошибка обновления статуса", show_alert=True)

@router.callback_query(F.data.startswith("toggle_lesson_status_"))
async def toggle_lesson_status(callback: CallbackQuery):
    """Переключить статус проведения занятия"""
    if not await check_admin_access_callback(callback):
        return
    
    lesson_id = int(callback.data.split("_")[-1])
    
    # Получаем информацию о занятии
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.answer("❌ Занятие не найдено", show_alert=True)
        return
    
    current_status = lesson.get('status', 'scheduled')
    
    # Переключаем статус
    new_status = 'completed' if current_status != 'completed' else 'scheduled'
    
    success = await db.update_lesson_status(lesson_id, new_status)
    
    if success:
        status_text = "✅ Проведено" if new_status == 'completed' else "⏳ Запланировано"
        await callback.answer(f"✅ Статус изменен: {status_text}", show_alert=True)
        # Обновляем отображение с актуальными данными
        await update_lesson_payment_message(callback, lesson_id)
    else:
        await callback.answer("❌ Ошибка обновления статуса", show_alert=True)

@router.callback_query(F.data.startswith("set_unpaid_"))
async def set_lesson_unpaid(callback: CallbackQuery):
    """Отметить занятие как неоплаченное"""
    if not await check_admin_access_callback(callback):
        return
        
    lesson_id = int(callback.data.split("_")[-1])
    
    success = await db.update_lesson_payment_status(lesson_id, 'unpaid')
    
    if success:
        await callback.answer("❌ Занятие отмечено как неоплаченное", show_alert=True)
        # Обновляем отображение с актуальными данными
        await update_lesson_payment_message(callback, lesson_id)
    else:
        await callback.answer("❌ Ошибка обновления статуса", show_alert=True)

@router.callback_query(F.data.startswith("confirm_delete_lesson_"))
async def confirm_delete_lesson(callback: CallbackQuery):
    """Подтверждение удаления занятия"""
    if not await check_admin_access_callback(callback):
        return
    
    lesson_id = int(callback.data.split("_")[-1])
    
    # Получаем информацию о занятии
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.answer("❌ Занятие не найдено", show_alert=True)
        return
    
    # Получаем информацию об ученике
    student = await db.get_student(lesson['student_id'])
    
    date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)
    
    message_text = (
        f"⚠️ <b>Подтверждение удаления</b>\n\n"
        f"Вы уверены, что хотите удалить это занятие?\n\n"
        f"👤 Ученик: {student['name']}\n"
        f"📅 Дата: {date_str} в {lesson['lesson_time']}\n"
        f"💰 Стоимость: {lesson['price']:.0f}₽\n"
        f"📊 Статус: {lesson['status']}\n"
        f"💵 Оплата: {lesson.get('payment_status', 'unpaid')}\n\n"
        f"⚠️ <b>Это действие нельзя отменить!</b>"
    )
    
    await callback.message.edit_text(
        message_text,
        reply_markup=kb.confirm_lesson_deletion_keyboard(lesson_id, lesson['student_id']),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("delete_lesson_notify_"))
async def delete_lesson_with_notification(callback: CallbackQuery, bot: Bot):
    """Удалить занятие с отправкой уведомления ученику"""
    if not await check_admin_access_callback(callback):
        return
    
    lesson_id = int(callback.data.split("_")[-1])
    
    # Получаем информацию о занятии перед удалением
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.answer("❌ Занятие не найдено", show_alert=True)
        return
    
    student_id = lesson['student_id']
    student = await db.get_student(student_id)
    
    # Отменяем все задачи для занятия
    try:
        from bot_template.database.task_manager import TaskManager
        task_manager = TaskManager(db)
        await task_manager.cancel_lesson_tasks(lesson_id)
    except Exception as task_error:
        logger.warning(f" Ошибка отмены задач для занятия #{lesson_id}: {task_error}")
    
    # Удаляем занятие
    success = await db.delete_lesson(lesson_id)
    
    if success:
        # Отправляем уведомление ученику
        date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)
        
        duration_hours = lesson['duration'] // 60
        duration_mins = lesson['duration'] % 60
        if duration_mins:
            duration_str = f"{duration_hours}ч {duration_mins}мин"
        else:
            duration_str = f"{duration_hours}ч"
        
        notification_text = (
            f"❌ <b>Занятие отменено</b>\n\n"
            f"📅 {date_str} в {lesson['lesson_time']}\n"
            f"⏱️ Продолжительность: {duration_str}\n"
            f"📍 Формат: {'онлайн' if lesson['lesson_format'] == 'online' else 'оффлайн'}\n\n"
            f"Если у вас есть вопросы, свяжитесь с преподавателем."
        )
        
        try:
            await bot.send_message(
                chat_id=student_id,
                text=notification_text,
                parse_mode="HTML"
            )
            logger.info(f" Отправлено уведомление об отмене занятия ученику {student['name']}")
        except Exception as e:
            logger.warning(f" Не удалось отправить уведомление ученику {student_id}: {e}")
        
        await callback.answer("✅ Занятие удалено, ученик уведомлен", show_alert=True)
        
        # Возвращаемся к списку занятий ученика
        await callback.message.edit_text(
            "✅ Занятие успешно удалено\n📤 Ученик уведомлен об отмене",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Вернуться в историю ученика", callback_data=f"lessons_history_{student_id}")],
                [InlineKeyboardButton(text="👤 К профилю", callback_data=f"view_student_{student_id}")]
            ])
        )
    else:
        await callback.answer("❌ Ошибка удаления занятия", show_alert=True)

@router.callback_query(F.data.startswith("delete_lesson_silent_"))
async def delete_lesson_without_notification(callback: CallbackQuery):
    """Удалить занятие без отправки уведомления ученику"""
    if not await check_admin_access_callback(callback):
        return
    
    lesson_id = int(callback.data.split("_")[-1])
    
    # Получаем информацию о занятии перед удалением
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.answer("❌ Занятие не найдено", show_alert=True)
        return
    
    student_id = lesson['student_id']
    
    # Отменяем все задачи для занятия
    try:
        from bot_template.database.task_manager import TaskManager
        task_manager = TaskManager(db)
        await task_manager.cancel_lesson_tasks(lesson_id)
    except Exception as task_error:
        logger.warning(f" Ошибка отмены задач для занятия #{lesson_id}: {task_error}")
    
    # Удаляем занятие
    success = await db.delete_lesson(lesson_id)
    
    if success:
        await callback.answer("✅ Занятие успешно удалено", show_alert=True)
        
        # Возвращаемся к списку занятий ученика
        await callback.message.edit_text(
            "✅ Занятие успешно удалено из базы данных",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Вернуться в историю ученика", callback_data=f"lessons_history_{student_id}")],
                [InlineKeyboardButton(text="👤 К профилю", callback_data=f"view_student_{student_id}")]
            ])
        )
    else:
        await callback.answer("❌ Ошибка удаления занятия", show_alert=True)


# === РАЗДЕЛ "ПЕРЕНОС ЗАНЯТИЙ" ===

@router.callback_query(F.data.startswith("reschedule_lesson_"))
async def start_reschedule_lesson(callback: CallbackQuery):
    """Начать процесс переноса занятия - выбор новой даты"""
    if not await check_admin_access_callback(callback):
        return

    lesson_id = int(callback.data.split("_")[-1])

    # Получаем информацию о занятии
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.answer("❌ Занятие не найдено", show_alert=True)
        return

    student = await db.get_student(lesson['student_id'])
    date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)

    message_text = (
        f"🔄 <b>Перенос занятия</b>\n\n"
        f"👤 Ученик: {student['name']}\n"
        f"📅 Текущая дата: {date_str}\n"
        f"🕐 Текущее время: {lesson['lesson_time']}\n"
        f"💰 Стоимость: {lesson['price']:.0f}₽\n\n"
        f"<b>Выберите новую дату:</b>"
    )

    now = get_local_time()
    calendar_kb = kb.calendar_keyboard(
        year=now.year,
        month=now.month,
        context="rs",
        extra_data=f"l{lesson_id}_s{lesson['student_id']}"
    )

    await callback.message.edit_text(
        message_text,
        reply_markup=calendar_kb,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("reschedule_date_"))
async def select_reschedule_date(callback: CallbackQuery, state: FSMContext):
    """Дата выбрана, выбираем время"""
    if not await check_admin_access_callback(callback):
        return

    parts = callback.data.split("_")
    lesson_id = int(parts[2])
    new_date = parts[3]

    # Получаем информацию о занятии
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.answer("❌ Занятие не найдено", show_alert=True)
        return

    student = await db.get_student(lesson['student_id'])

    # Форматируем новую дату
    from datetime import datetime
    new_date_obj = datetime.strptime(new_date, '%Y-%m-%d')
    weekdays = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}
    weekday = weekdays[new_date_obj.weekday()]
    new_date_display = f"{new_date_obj.strftime('%d.%m.%Y')} ({weekday})"

    old_date_display = format_date_with_weekday(lesson['lesson_date'], full_format=True)

    message_text = (
        f"🔄 <b>Перенос занятия</b>\n\n"
        f"👤 Ученик: {student['name']}\n"
        f"📅 С даты: {old_date_display} → <b>{new_date_display}</b>\n"
        f"🕐 Текущее время: {lesson['lesson_time']}\n\n"
        f"<b>Выберите новое время:</b>"
    )

    await callback.message.edit_text(
        message_text,
        reply_markup=kb.reschedule_time_keyboard(lesson_id, new_date, lesson['student_id']),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("reschedule_time_"))
async def confirm_reschedule(callback: CallbackQuery, state: FSMContext):
    """Время выбрано, подтверждаем перенос"""
    if not await check_admin_access_callback(callback):
        return

    parts = callback.data.split("_")
    lesson_id = int(parts[2])
    new_date = parts[3]
    new_time = parts[4]

    # Получаем информацию о занятии
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.answer("❌ Занятие не найдено", show_alert=True)
        return

    student = await db.get_student(lesson['student_id'])

    # Форматируем даты
    from datetime import datetime
    new_date_obj = datetime.strptime(new_date, '%Y-%m-%d')
    weekdays = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}
    weekday = weekdays[new_date_obj.weekday()]
    new_date_display = f"{new_date_obj.strftime('%d.%m.%Y')} ({weekday})"

    old_date_display = format_date_with_weekday(lesson['lesson_date'], full_format=True)

    # Сохраняем данные в state для подтверждения
    await state.update_data(
        reschedule_lesson_id=lesson_id,
        reschedule_new_date=new_date,
        reschedule_new_time=new_time,
        reschedule_student_id=lesson['student_id']
    )

    message_text = (
        f"🔄 <b>Подтверждение переноса</b>\n\n"
        f"👤 Ученик: {student['name']}\n\n"
        f"<b>Было:</b>\n"
        f"📅 {old_date_display}\n"
        f"🕐 {lesson['lesson_time']}\n\n"
        f"<b>Станет:</b>\n"
        f"📅 {new_date_display}\n"
        f"🕐 {new_time}\n\n"
        f"💰 Стоимость: {lesson['price']:.0f}₽\n"
        f"📝 ДЗ: {'Сохранится' if lesson.get('homework') else 'Нет'}\n"
        f"💵 Оплата: {lesson.get('payment_status', 'unpaid')}\n\n"
        f"⚠️ Все данные занятия (ДЗ, цена, статусы) будут сохранены."
    )

    await callback.message.edit_text(
        message_text,
        reply_markup=kb.confirm_reschedule_keyboard(lesson_id, lesson['student_id']),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("reschedule_custom_time_"))
async def request_custom_time(callback: CallbackQuery, state: FSMContext):
    """Запросить ввод своего времени"""
    if not await check_admin_access_callback(callback):
        return

    parts = callback.data.split("_")
    lesson_id = int(parts[3])
    new_date = parts[4]

    # Сохраняем данные в state
    await state.update_data(
        reschedule_lesson_id=lesson_id,
        reschedule_new_date=new_date
    )
    # Устанавливаем state для ввода времени
    await state.set_state(AdminPanelStates.entering_reschedule_custom_time)

    await callback.message.edit_text(
        "⌨️ <b>Введите новое время</b>\n\n"
        "Формат: ЧЧ:ММ (например, 14:30)\n\n"
        "Или отправьте /cancel для отмены",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminPanelStates.entering_reschedule_custom_time)
async def process_custom_time(message: Message, state: FSMContext):
    """Обработка введенного времени"""
    if message.text == '/cancel':
        await state.clear()
        await message.answer("❌ Отменено")
        return

    # Проверяем формат времени
    import re
    time_pattern = r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$'
    if not re.match(time_pattern, message.text):
        await message.answer(
            "❌ Неверный формат времени\n\n"
            "Используйте формат ЧЧ:ММ (например, 14:30)"
        )
        return

    data = await state.get_data()
    lesson_id = data['reschedule_lesson_id']
    new_date = data['reschedule_new_date']
    new_time = message.text

    # Получаем информацию о занятии
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await message.answer("❌ Занятие не найдено")
        await state.clear()
        return

    student = await db.get_student(lesson['student_id'])

    # Форматируем даты
    from datetime import datetime
    new_date_obj = datetime.strptime(new_date, '%Y-%m-%d')
    weekdays = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}
    weekday = weekdays[new_date_obj.weekday()]
    new_date_display = f"{new_date_obj.strftime('%d.%m.%Y')} ({weekday})"

    old_date_display = format_date_with_weekday(lesson['lesson_date'], full_format=True)

    # Сохраняем данные для подтверждения
    await state.update_data(
        reschedule_new_time=new_time,
        reschedule_student_id=lesson['student_id']
    )

    message_text = (
        f"🔄 <b>Подтверждение переноса</b>\n\n"
        f"👤 Ученик: {student['name']}\n\n"
        f"<b>Было:</b>\n"
        f"📅 {old_date_display}\n"
        f"🕐 {lesson['lesson_time']}\n\n"
        f"<b>Станет:</b>\n"
        f"📅 {new_date_display}\n"
        f"🕐 {new_time}\n\n"
        f"💰 Стоимость: {lesson['price']:.0f}₽\n"
        f"📝 ДЗ: {'Сохранится' if lesson.get('homework') else 'Нет'}\n"
        f"💵 Оплата: {lesson.get('payment_status', 'unpaid')}\n\n"
        f"⚠️ Все данные занятия (ДЗ, цена, статусы) будут сохранены."
    )

    await message.answer(
        message_text,
        reply_markup=kb.confirm_reschedule_keyboard(lesson_id, lesson['student_id']),
        parse_mode="HTML"
    )

    # Очищаем state ввода времени, чтобы можно было использовать reply кнопки
    await state.set_state(None)


@router.callback_query(F.data.startswith("confirm_reschedule_notify_"))
async def execute_reschedule_with_notification(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Выполнить перенос занятия с уведомлением"""
    await _execute_reschedule(callback, state, bot, send_notification=True)


@router.callback_query(F.data.startswith("confirm_reschedule_silent_"))
async def execute_reschedule_without_notification(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Выполнить перенос занятия без уведомления"""
    await _execute_reschedule(callback, state, bot, send_notification=False)


async def _execute_reschedule(callback: CallbackQuery, state: FSMContext, bot: Bot, send_notification: bool):
    """Выполнить перенос занятия"""
    if not await check_admin_access_callback(callback):
        return

    lesson_id = int(callback.data.split("_")[-1])
    data = await state.get_data()

    new_date = data.get('reschedule_new_date')
    new_time = data.get('reschedule_new_time')

    if not new_date or not new_time:
        await callback.answer("❌ Ошибка: данные не найдены", show_alert=True)
        return

    # Получаем информацию о занятии до переноса
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.answer("❌ Занятие не найдено", show_alert=True)
        return

    old_date = lesson['lesson_date']
    old_time = lesson['lesson_time']
    student_id = lesson['student_id']
    student = await db.get_student(student_id)

    # Выполняем перенос
    success = await db.reschedule_lesson(lesson_id, new_date, new_time)

    if success:
        # Отменяем старые задачи
        try:
            from bot_template.database.task_manager import TaskManager
            task_manager = TaskManager(db)
            await task_manager.cancel_lesson_tasks(lesson_id)

            # Создаем новые задачи
            updated_lesson = await db.get_lesson_by_id(lesson_id)
            if updated_lesson:
                await task_manager.schedule_lesson_tasks(updated_lesson, days_ahead=30)
        except Exception as task_error:
            logger.warning(f"Ошибка обновления задач для занятия #{lesson_id}: {task_error}")

        # Форматируем даты для уведомления
        old_date_display = format_date_with_weekday(old_date, full_format=True)
        from datetime import datetime
        new_date_obj = datetime.strptime(new_date, '%Y-%m-%d')
        weekdays = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}
        weekday = weekdays[new_date_obj.weekday()]
        new_date_display = f"{new_date_obj.strftime('%d.%m.%Y')} ({weekday})"

        # Отправляем уведомление ученику, только если send_notification=True
        notification_status = ""
        if send_notification:
            notification_text = (
                f"🔄 <b>Занятие перенесено</b>\n\n"
                f"<b>Было:</b>\n"
                f"📅 {old_date_display} в {old_time}\n\n"
                f"<b>Теперь:</b>\n"
                f"📅 {new_date_display} в {new_time}\n\n"
                f"Все данные занятия сохранены (ДЗ, оплата)."
            )

            try:
                await bot.send_message(
                    chat_id=student_id,
                    text=notification_text,
                    parse_mode="HTML"
                )
                logger.info(f"Отправлено уведомление о переносе ученику {student['name']}")
                notification_status = "📤 Ученик уведомлен о переносе"
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление ученику {student_id}: {e}")
                notification_status = "⚠️ Не удалось отправить уведомление"
        else:
            notification_status = "🔕 Уведомление не отправлено"

        await callback.answer("✅ Занятие успешно перенесено", show_alert=True)
        await callback.message.edit_text(
            f"✅ <b>Занятие успешно перенесено!</b>\n\n"
            f"👤 Ученик: {student['name']}\n"
            f"📅 Новая дата: {new_date_display}\n"
            f"🕐 Новое время: {new_time}\n\n"
            f"{notification_status}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ К списку занятий", callback_data=f"lessons_history_{student_id}")],
                [InlineKeyboardButton(text="👤 К профилю", callback_data=f"view_student_{student_id}")]
            ]),
            parse_mode="HTML"
        )

        # Очищаем state
        await state.clear()
    else:
        await callback.answer("❌ Ошибка переноса занятия", show_alert=True)


@router.callback_query(F.data.startswith("cancel_reschedule_"))
async def cancel_reschedule(callback: CallbackQuery, state: FSMContext):
    """Отменить перенос занятия"""
    if not await check_admin_access_callback(callback):
        return

    parts = callback.data.split("_")
    lesson_id = int(parts[2])
    student_id = int(parts[3])

    # Очищаем state
    await state.clear()

    # Возвращаемся к занятию
    await callback.answer("❌ Перенос отменен")

    # Получаем информацию о занятии
    lesson = await db.get_lesson_by_id(lesson_id)
    if lesson:
        # Показываем информацию о занятии с клавиатурой управления
        from bot_template.app.handlers import show_lesson_management
        await show_lesson_management_for_reschedule(callback, lesson_id, student_id)
    else:
        await callback.message.edit_text(
            "❌ Занятие не найдено",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ К списку занятий", callback_data=f"lessons_history_{student_id}")]
            ])
        )


async def show_lesson_management_for_reschedule(callback: CallbackQuery, lesson_id: int, student_id: int):
    """Вспомогательная функция для отображения управления занятием после отмены переноса"""
    lesson = await db.get_lesson_by_id(lesson_id)
    if not lesson:
        return

    student = await db.get_student(student_id)
    date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)

    duration_hours = lesson['duration'] // 60
    duration_mins = lesson['duration'] % 60
    if duration_mins:
        duration_str = f"{duration_hours}ч {duration_mins}мин"
    else:
        duration_str = f"{duration_hours}ч"

    payment_emoji = "✅" if lesson['payment_status'] == 'paid' else "❌"
    payment_text = "оплачено" if lesson['payment_status'] == 'paid' else "не оплачено"

    status_emoji = "✅" if lesson['status'] == 'completed' else "📅"
    status_text = "проведено" if lesson['status'] == 'completed' else "запланировано"

    homework_text = lesson.get('homework', 'Не задано')
    if lesson.get('homework_status') == 'completed':
        homework_emoji = "✅"
    elif lesson.get('homework'):
        homework_emoji = "📝"
    else:
        homework_emoji = "📭"

    message_text = (
        f"📚 <b>Занятие #{lesson_id}</b>\n\n"
        f"👤 Ученик: {student['name']}\n"
        f"📅 Дата: {date_str}\n"
        f"🕐 Время: {lesson['lesson_time']}\n"
        f"⏱️ Продолжительность: {duration_str}\n"
        f"💰 Стоимость: {lesson['price']:.0f}₽\n"
        f"{status_emoji} Статус: {status_text}\n"
        f"{payment_emoji} Оплата: {payment_text}\n\n"
        f"{homework_emoji} ДЗ: {homework_text}"
    )

    await callback.message.edit_text(
        message_text,
        reply_markup=kb.lesson_payment_keyboard(
            lesson_id, student_id,
            lesson['payment_status'],
            lesson['status']
        ),
        parse_mode="HTML"
    )


# === РАЗДЕЛ "ДОЛЖНИКИ" В АДМИН-ПАНЕЛИ ===

@router.message(F.text == '💰 Должники')
async def show_debtors_menu(message: Message):
    """Показать список учеников с задолженностью"""
    if not await check_admin_access(message):
        return
    
    # Получаем список должников
    debtors = await db.get_all_debtors()
    
    if not debtors:
        await message.answer(
            "✅ <b>Отлично! Задолженностей нет</b>\n\n"
            "Все ученики оплатили свои занятия 🎉",
            parse_mode="HTML"
        )
        return
    
    # Считаем общую задолженность
    total_debt = sum(d['total_debt'] for d in debtors)
    total_lessons = sum(d['unpaid_count'] for d in debtors)
    
    message_text = (
        f"💰 <b>СПИСОК ДОЛЖНИКОВ</b>\n\n"
        f"📊 Всего должников: {len(debtors)}\n"
        f"💵 Общая задолженность: <b>{total_debt:.0f}₽</b>\n"
        f"📅 Неоплаченных занятий: {total_lessons}\n\n"
        f"Выберите ученика для подробной информации:"
    )
    
    await message.answer(
        message_text,
        reply_markup=kb.debtors_list_keyboard(debtors),
        parse_mode="HTML"
    )

# === РАЗДЕЛ "ИЗМЕНЕНИЯ УЧЕНИКОВ" В АДМИН-ПАНЕЛИ ===

@router.message(F.text == "📝 Изменения учеников")
async def show_student_changes(message: Message):
    """Показать список учеников, которые меняли профиль за последнюю неделю"""
    if not await check_admin_access(message):
        return
    
    students_with_changes = await db.get_student_changes_last_week()
    
    if not students_with_changes:
        await message.answer(
            "📝 <b>Изменения учеников</b>\n\n"
            "✅ За последнюю неделю никто не менял свой профиль.",
            reply_markup=kb.admin_main,
            parse_mode="HTML"
        )
        return
    
    message_text = (
        f"📝 <b>ИЗМЕНЕНИЯ УЧЕНИКОВ</b>\n"
        f"За последнюю неделю:\n\n"
        f"Всего учеников с изменениями: {len(students_with_changes)}\n\n"
        f"Выберите ученика для просмотра деталей:"
    )
    
    await message.answer(
        message_text,
        reply_markup=kb.student_changes_list_keyboard(students_with_changes),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "show_student_changes")
async def show_student_changes_callback(callback: CallbackQuery):
    """Обработчик возврата к списку изменений"""
    if not await check_admin_access_callback(callback):
        return
    
    students_with_changes = await db.get_student_changes_last_week()
    
    if not students_with_changes:
        await callback.message.edit_text(
            "📝 <b>Изменения учеников</b>\n\n"
            "✅ За последнюю неделю никто не менял свой профиль.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_admin")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    message_text = (
        f"📝 <b>ИЗМЕНЕНИЯ УЧЕНИКОВ</b>\n"
        f"За последнюю неделю:\n\n"
        f"Всего учеников с изменениями: {len(students_with_changes)}\n\n"
        f"Выберите ученика для просмотра деталей:"
    )
    
    await callback.message.edit_text(
        message_text,
        reply_markup=kb.student_changes_list_keyboard(students_with_changes),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("student_changes_"))
async def show_student_changes_details(callback: CallbackQuery):
    """Показать детали изменений конкретного ученика"""
    if not await check_admin_access_callback(callback):
        return
    
    try:
        student_id = int(callback.data.split("_")[2])
        
        # Получаем данные ученика
        student = await db.get_student(student_id)
        if not student:
            await callback.answer("❌ Ученик не найден", show_alert=True)
            return
        
        # Получаем изменения за неделю
        changes = await db.get_student_changes(student_id, days=7)
        
        if not changes:
            await callback.message.edit_text(
                f"📝 <b>Изменения: {student['name']}</b>\n\n"
                "✅ За последнюю неделю изменений не было.",
                reply_markup=kb.student_changes_details_keyboard(student_id),
                parse_mode="HTML"
            )
            await callback.answer()
            return
        
        # Формируем сообщение с деталями
        change_type_names = {
            'name': 'Имя',
            'grade': 'Класс',
            'subject': 'Направление'
        }
        
        message_text = f"📝 <b>ИЗМЕНЕНИЯ: {student['name']}</b>\n\n"
        message_text += "За последнюю неделю:\n\n"
        
        for change in changes:
            change_type = change_type_names.get(change['change_type'], change['change_type'])
            old_value = change['old_value'] or '(не указано)'
            new_value = change['new_value'] or '(не указано)'
            
            # Форматируем дату
            change_date = change['change_date']
            try:
                date_obj = datetime.strptime(change_date, '%Y-%m-%d %H:%M:%S')
                date_str = date_obj.strftime('%d.%m.%Y %H:%M')
            except:
                date_str = change_date
            
            changed_by_text = "учителем" if change['changed_by'] == 'teacher' else "учеником"
            
            message_text += (
                f"• <b>{change_type}:</b> {old_value} → {new_value}\n"
                f"  📅 {date_str} ({changed_by_text})\n\n"
            )
        
        await callback.message.edit_text(
            message_text,
            reply_markup=kb.student_changes_details_keyboard(student_id),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f" Ошибка в show_student_changes_details: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

# === РАЗДЕЛ "РАСПИСАНИЕ" В АДМИН-ПАНЕЛИ ===

@router.message(F.text == '📅 Расписание')
async def show_schedule_today(message: Message):
    """Показать расписание на сегодня"""
    if not await check_admin_access(message):
        return
    
    try:
        today_lessons = await db.get_today_lessons()
        
        # Получаем текущую дату для заголовка
        today = get_local_time().date()
        weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        weekday_name = weekday_names[today.weekday()]
        date_str = today.strftime('%d.%m.%Y')
        
        message_text = f"📅 <b>РАСПИСАНИЕ НА СЕГОДНЯ</b>\n{date_str} ({weekday_name})\n\n"
        
        if not today_lessons:
            message_text += "✅ На сегодня занятий нет"
        else:
            for lesson in today_lessons:
                time_str = format_lesson_time(lesson['lesson_time'], lesson.get('duration', 60))
                
                # Мини-информация об ученике
                student_name = lesson['student_name']
                grade = lesson.get('grade', '')
                subject = lesson.get('subject', '')
                student_info = f"{student_name}"
                if grade:
                    student_info += f" ({grade}кл"
                    if subject:
                        student_info += f", {subject}"
                    student_info += ")"
                
                # ДЗ (обрезаем для мобильных)
                homework = (lesson.get('homework') or '').strip()
                if len(homework) > 50:
                    homework = homework[:47] + "..."
                
                # Цена
                price = int(lesson.get('price', 0))
                
                time_str = format_lesson_time(lesson['lesson_time'], lesson.get('duration', 60))
                message_text += f"🕐 <b>{time_str}</b>\n"
                message_text += f"👤 {student_info}\n"
                if homework:
                    message_text += f"📝 {homework}\n"
                message_text += f"💰 {price}₽\n\n"
        
        await message.answer(
            message_text,
            reply_markup=kb.schedule_today_keyboard(),
            parse_mode="HTML"
        )
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f" Ошибка в show_schedule_today: {error_details}")
        await message.answer(
            "❌ Произошла ошибка при загрузке расписания",
            reply_markup=kb.admin_main
        )

@router.callback_query(F.data == "show_debtors")
async def show_debtors_callback(callback: CallbackQuery):
    """Показать список должников (callback версия)"""
    if not await check_admin_access_callback(callback):
        return
    
    # Получаем список должников
    debtors = await db.get_all_debtors()
    
    if not debtors:
        await callback.message.edit_text(
            "✅ <b>Отлично! Задолженностей нет</b>\n\n"
            "Все ученики оплатили свои занятия 🎉",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    # Считаем общую задолженность
    total_debt = sum(d['total_debt'] for d in debtors)
    total_lessons = sum(d['unpaid_count'] for d in debtors)
    
    message_text = (
        f"💰 <b>СПИСОК ДОЛЖНИКОВ</b>\n\n"
        f"📊 Всего должников: {len(debtors)}\n"
        f"💵 Общая задолженность: <b>{total_debt:.0f}₽</b>\n"
        f"📅 Неоплаченных занятий: {total_lessons}\n\n"
        f"Выберите ученика для подробной информации:"
    )
    
    await callback.message.edit_text(
        message_text,
        reply_markup=kb.debtors_list_keyboard(debtors),
        parse_mode="HTML"
    )
    await callback.answer()

# === ХЕНДЛЕРЫ ДЛЯ ФИЛЬТРОВ ИСТОРИИ ЗАНЯТИЙ ===

@router.callback_query(F.data.startswith("change_history_filter_"))
async def change_history_filter(callback: CallbackQuery):
    """Показать меню выбора фильтра"""
    if not await check_admin_access_callback(callback):
        return
    
    student_id = int(callback.data.split("_")[-1])
    
    await callback.message.edit_text(
        "🔄 <b>Выберите фильтр для истории занятий:</b>\n\n"
        "🎯 <b>Умный фильтр</b> (рекомендуется)\n"
        "• Неоплаченные занятия (все)\n"
        "• Предстоящие на неделю\n"
        "• Прошедшие за неделю\n\n"
        "❌ <b>Только неоплаченные</b>\n"
        "• Показать все долги\n\n"
        "📅 <b>Все занятия</b>\n"
        "• Полная история без фильтров",
        reply_markup=kb.history_filter_keyboard(student_id),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("history_filter_smart_"))
async def apply_smart_filter(callback: CallbackQuery):
    """Применить умный фильтр"""
    if not await check_admin_access_callback(callback):
        return
    
    student_id = int(callback.data.split("_")[-1])
    await show_lessons_with_filter(callback, student_id, "smart")

@router.callback_query(F.data.startswith("history_filter_unpaid_"))
async def apply_unpaid_filter(callback: CallbackQuery):
    """Применить фильтр неоплаченных"""
    if not await check_admin_access_callback(callback):
        return
    
    student_id = int(callback.data.split("_")[-1])
    await show_lessons_with_filter(callback, student_id, "unpaid")

@router.callback_query(F.data.startswith("history_filter_all_"))
async def apply_all_filter(callback: CallbackQuery):
    """Показать все занятия"""
    if not await check_admin_access_callback(callback):
        return
    
    student_id = int(callback.data.split("_")[-1])
    await show_lessons_with_filter(callback, student_id, "all")

@router.callback_query(F.data.startswith("debtor_details_"))
async def show_debtor_details(callback: CallbackQuery):
    """Показать детальную информацию о задолженности ученика"""
    if not await check_admin_access_callback(callback):
        return
    
    student_id = int(callback.data.split("_")[-1])
    
    # Получаем информацию об ученике
    student = await db.get_student(student_id)
    if not student:
        await callback.answer("❌ Ученик не найден", show_alert=True)
        return
    
    # Получаем неоплаченные занятия
    unpaid_lessons = await db.get_student_unpaid_lessons(student_id)
    
    if not unpaid_lessons:
        await callback.answer("✅ У ученика нет задолженностей", show_alert=True)
        return
    
    # Считаем задолженность
    total_debt = sum(l['price'] for l in unpaid_lessons)
    
    # Формируем сообщение (компактно для мобильных)
    username_text = student['username'] if student['username'] else "нет username"
    
    message_text = (
        f"💰 <b>Долг: {student['name']}</b>\n"
        f"📱 {username_text} | 📞 {student['phone']}\n"
        f"🎓 Класс {student['grade']}\n\n"
        f"💵 <b>Долг: {total_debt:.0f}₽</b> ({len(unpaid_lessons)} занятий)\n\n"
    )
    
    # Добавляем список занятий (компактно)
    for lesson in unpaid_lessons[:15]:
        date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)
        time_str = format_lesson_time(lesson['lesson_time'], lesson.get('duration', 60))
        hw_text = " 📖ДЗ" if lesson.get('homework') else ""
        message_text += f"❌ {date_str} {time_str}, {lesson['price']:.0f}₽{hw_text}\n"
    
    if len(unpaid_lessons) > 15:
        message_text += f"... и еще {len(unpaid_lessons) - 15} занятий\n"
    
    await callback.message.edit_text(
        message_text,
        reply_markup=kb.debtor_details_keyboard(student_id),
        parse_mode="HTML"
    )
    await callback.answer()


# ============= ТЕСТОВЫЕ ФУНКЦИИ =============

@router.message(Command("test_notification"))
async def test_notification_command(message: Message):
    """Тестовая команда для проверки уведомлений о занятиях"""
    # Проверка прав администратора
    if message.from_user.id not in ADMINS_IDS:
        await message.answer("⛔ Эта команда доступна только администраторам")
        return
    
    try:
        # Получаем ближайшее запланированное занятие
        async with aiosqlite.connect(DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("""
                SELECT l.*, s.name as student_name
                FROM lessons l
                JOIN students s ON l.student_id = s.user_id
                WHERE l.status = 'scheduled'
                AND l.lesson_date >= date('now')
                ORDER BY l.lesson_date ASC, l.lesson_time ASC
                LIMIT 1
            """)
            lesson = await cursor.fetchone()
        
        if not lesson:
            await message.answer(
                "❌ Нет запланированных занятий для тестирования\n\n"
                "Создайте расписание или добавьте занятие вручную"
            )
            return
        
        lesson = dict(lesson)
        
        # Формируем тестовое уведомление
        date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)
        
        duration_hours = lesson['duration'] // 60
        duration_mins = lesson['duration'] % 60
        duration_str = f"{duration_hours}ч {duration_mins}мин" if duration_mins else f"{duration_hours}ч"
        
        payment_emoji = "💰" if lesson['payment_status'] == 'paid' else "❌"
        payment_text = "оплачено" if lesson['payment_status'] == 'paid' else "не оплачено"
        
        test_message = (
            f"🧪 <b>ТЕСТОВОЕ УВЕДОМЛЕНИЕ</b>\n\n"
            f"⏰ Занятие завершается через 5 минут!\n\n"
            f"👤 Ученик: {lesson['student_name']}\n"
            f"📅 {date_str} в {lesson['lesson_time']}\n"
            f"⏱️ Продолжительность: {duration_str}\n"
            f"{payment_emoji} Оплата: {payment_text}\n\n"
            f"📝 Не забудьте отметить статус оплаты и задать домашнее задание!"
        )
        
        # Отправляем уведомление с клавиатурой
        await message.answer(
            test_message,
            reply_markup=kb.lesson_ending_keyboard(lesson['id'], lesson.get('student_id')),
            parse_mode="HTML"
        )
        
        # Информация о тестировании
        await message.answer(
            f"✅ Тестовое уведомление отправлено!\n\n"
            f"📊 Данные занятия:\n"
            f"• ID: {lesson['id']}\n"
            f"• Дата: {lesson['lesson_date']}\n"
            f"• Время: {lesson['lesson_time']}\n"
            f"• Ученик: {lesson['student_name']} (ID: {lesson['student_id']})\n\n"
            f"ℹ️ Кнопки работают в реальном режиме - изменения будут сохранены в БД"
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при тестировании: {str(e)}")


@router.message(Command("test_student_notification"))
async def test_student_notification_command(message: Message):
    """Тестовая команда для проверки уведомлений ученикам"""
    # Проверка прав администратора
    if message.from_user.id not in ADMINS_IDS:
        await message.answer("⛔ Эта команда доступна только администраторам")
        return
    
    try:
        # Получаем ближайшее запланированное занятие
        async with aiosqlite.connect(DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("""
                SELECT l.*, s.name as student_name, s.user_id
                FROM lessons l
                JOIN students s ON l.student_id = s.user_id
                WHERE l.status = 'scheduled'
                AND l.lesson_date >= date('now')
                ORDER BY l.lesson_date ASC, l.lesson_time ASC
                LIMIT 1
            """)
            lesson = await cursor.fetchone()
        
        if not lesson:
            await message.answer(
                "❌ Нет запланированных занятий для тестирования\n\n"
                "Создайте расписание или добавьте занятие вручную"
            )
            return
        
        lesson = dict(lesson)
        student_id = lesson['user_id']
        
        # Получаем задолженность ученика
        debt_info = await db.get_student_debt(student_id)
        
        # Формируем тестовое уведомление для ученика
        date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)
        
        duration_hours = lesson['duration'] // 60
        duration_mins = lesson['duration'] % 60
        duration_str = f"{duration_hours}ч {duration_mins}мин" if duration_mins else f"{duration_hours}ч"
        
        student_message = (
            f"🧪 <b>ТЕСТОВОЕ НАПОМИНАНИЕ</b>\n\n"
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
        
        # Отправляем тестовое уведомление
        await message.answer(student_message, parse_mode="HTML")
        
        # Информация о тестировании
        await message.answer(
            f"✅ Тестовое уведомление (для ученика) отправлено!\n\n"
            f"📊 Данные:\n"
            f"• Ученик: {lesson['student_name']} (ID: {student_id})\n"
            f"• Задолженность: {debt_info['total_debt']:.0f}₽\n"
            f"• Неоплаченных занятий: {debt_info['unpaid_count']}\n\n"
            f"ℹ️ В реальном режиме это сообщение отправляется ученику за 3 часа до занятия"
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при тестировании: {str(e)}")


@router.message(Command("check_ending_now"))
async def check_ending_lessons_now(message: Message, bot: Bot):
    """Команда для немедленной проверки занятий, заканчивающихся через 5 минут"""
    # Проверка прав администратора
    if message.from_user.id not in ADMINS_IDS:
        await message.answer("⛔ Эта команда доступна только администраторам")
        return
    
    try:
        # Получаем все занятия с отладкой
        lessons = await db.get_lessons_ending_soon(minutes_before=5, debug=True)
        
        # Формируем отчет
        now = get_local_time()
        report = f"🔍 <b>ОТЧЕТ О ПРОВЕРКЕ</b>\n\n"
        report += f"⏰ Текущее время: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"📅 Проверяем занятия на: {now.strftime('%Y-%m-%d')}\n\n"
        
        if not lessons:
            report += "❌ <b>Не найдено занятий, заканчивающихся через 5 минут</b>\n\n"
            report += "Возможные причины:\n"
            report += "• Нет занятий на сегодня\n"
            report += "• Занятия еще не начались\n"
            report += "• Занятия уже закончились\n"
            report += "• До окончания не 5 минут (диапазон 3-7 минут)\n"
            report += "• Статус занятий не 'scheduled'\n\n"
            report += "💡 Проверьте логи бота для детальной информации"
        else:
            report += f"✅ <b>Найдено занятий: {len(lessons)}</b>\n\n"
            for lesson in lessons:
                lesson_start_naive = datetime.strptime(
                    f"{lesson['lesson_date']} {lesson['lesson_time']}", 
                    '%Y-%m-%d %H:%M'
                )
                # Добавляем часовой пояс (московское время)
                lesson_start = lesson_start_naive.replace(tzinfo=MOSCOW_TZ)
                duration = lesson.get('duration', 60)
                lesson_end = lesson_start + timedelta(minutes=duration)
                time_until_end = (lesson_end - now).total_seconds() / 60
                
                report += f"📚 <b>Занятие #{lesson['id']}</b>\n"
                report += f"👤 Ученик: {lesson['student_name']}\n"
                report += f"🕐 Начало: {lesson['lesson_time']}\n"
                report += f"⏱️ Продолжительность: {duration} мин\n"
                report += f"🕐 Окончание: {lesson_end.strftime('%H:%M')}\n"
                report += f"⏰ До окончания: {time_until_end:.1f} мин\n\n"
        
        await message.answer(report, parse_mode="HTML")
        
        # Вызываем проверку для отправки уведомлений
        from bot_template.run import check_ending_lessons
        await check_ending_lessons(db, bot)
        
        if lessons:
            await message.answer("✅ Уведомления отправлены учителю!")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при проверке: {str(e)}")
        import traceback
        traceback.print_exc()


# === ИНЛАЙН-КАЛЕНДАРЬ: ОБРАБОТЧИКИ ===

@router.callback_query(F.data == "cal_i")
async def calendar_ignore(callback: CallbackQuery):
    """Игнор клика по пустым ячейкам и заголовкам календаря"""
    await callback.answer()


@router.callback_query(F.data.startswith("cal_d_"))
async def calendar_day_selected(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора дня в календаре"""
    if not await check_admin_access_callback(callback):
        return

    try:
        # cal_d_{ctx}_{Y}_{M}_{D}_{extra...}
        parts = callback.data.split("_")
        context = parts[2]
        year = int(parts[3])
        month = int(parts[4])
        day = int(parts[5])
        extra = "_".join(parts[6:]) if len(parts) > 6 else ""

        from datetime import date as date_cls
        selected = date_cls(year, month, day)

        if selected < get_local_time().date():
            await callback.answer("❌ Нельзя выбрать дату в прошлом!", show_alert=True)
            return

        selected_str = selected.strftime('%Y-%m-%d')

        if context == "cl":
            # Создание занятия — extra = s{student_id}
            student_id = int(extra.lstrip("s"))
            student = await db.get_student(student_id)
            if not student:
                await callback.answer("❌ Ученик не найден", show_alert=True)
                return

            await state.update_data(lesson_date=selected_str)
            await state.set_state(AdminPanelStates.creating_lesson_time)

            date_display = format_date_with_weekday(selected_str, full_format=True)
            await callback.message.edit_text(
                f"➕ <b>ДОБАВЛЕНИЕ ЗАНЯТИЯ</b>\n\n"
                f"👤 Ученик: <b>{student['name']}</b>\n"
                f"📅 Дата: <b>{date_display}</b>\n\n"
                f"🕐 Введите время занятия в формате ЧЧ:ММ (например: 18:00):",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"view_student_{student_id}")]
                ]),
                parse_mode="HTML"
            )

        elif context == "rs":
            # Перенос занятия — extra = l{lesson_id}_s{student_id}
            extra_parts = extra.split("_")
            lesson_id = int(extra_parts[0].lstrip("l"))
            student_id = int(extra_parts[1].lstrip("s")) if len(extra_parts) > 1 else None

            lesson = await db.get_lesson_by_id(lesson_id)
            if not lesson:
                await callback.answer("❌ Занятие не найдено", show_alert=True)
                return

            student = await db.get_student(lesson['student_id'])
            new_date_display = format_date_with_weekday(selected_str, full_format=True)
            old_date_display = format_date_with_weekday(lesson['lesson_date'], full_format=True)

            await callback.message.edit_text(
                f"🔄 <b>Перенос занятия</b>\n\n"
                f"👤 Ученик: {student['name']}\n"
                f"📅 С даты: {old_date_display} → <b>{new_date_display}</b>\n"
                f"🕐 Текущее время: {lesson['lesson_time']}\n\n"
                f"<b>Выберите новое время:</b>",
                reply_markup=kb.reschedule_time_keyboard(lesson_id, selected_str, lesson['student_id']),
                parse_mode="HTML"
            )

        await callback.answer()

    except Exception as e:
        logger.error(f"calendar_day_selected error: {e}")
        await callback.answer("❌ Ошибка при выборе даты", show_alert=True)


@router.callback_query(F.data.startswith("cal_n_"))
async def calendar_navigate(callback: CallbackQuery):
    """Навигация по месяцам календаря"""
    if not await check_admin_access_callback(callback):
        return

    try:
        # cal_n_{ctx}_{Y}_{M}_{extra...}
        parts = callback.data.split("_")
        context = parts[2]
        year = int(parts[3])
        month = int(parts[4])
        extra = "_".join(parts[5:]) if len(parts) > 5 else ""

        calendar_kb = kb.calendar_keyboard(year, month, context, extra)

        await callback.message.edit_reply_markup(reply_markup=calendar_kb)
        await callback.answer()

    except Exception as e:
        logger.error(f"calendar_navigate error: {e}")
        await callback.answer("❌ Ошибка навигации", show_alert=True)


@router.callback_query(F.data.startswith("cal_b_"))
async def calendar_back(callback: CallbackQuery, state: FSMContext):
    """Кнопка 'Назад' в календаре"""
    if not await check_admin_access_callback(callback):
        return

    try:
        # cal_b_{ctx}_{extra...}
        parts = callback.data.split("_")
        context = parts[2]
        extra = "_".join(parts[3:]) if len(parts) > 3 else ""

        # Извлекаем student_id из extra
        # cl: extra = "s123"
        # rs: extra = "l456_s123"
        student_id = None
        for part in extra.split("_"):
            if part.startswith("s"):
                student_id = int(part[1:])
                break

        await state.clear()

        if student_id:
            await show_student_card_internal(callback, student_id, state)
        else:
            await callback.answer("❌ Ошибка возврата", show_alert=True)

    except Exception as e:
        logger.error(f"calendar_back error: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)