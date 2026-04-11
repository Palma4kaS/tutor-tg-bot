"""Обработчики занятий: создание, история, оплата, удаление."""

from datetime import datetime, timedelta
from typing import Dict

import aiosqlite
from aiogram import F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from config import ADMINS_IDS, TUTOR_ID, DB_PATH, ONLINE, OFFLINE, PROFIL, CLASS_10_11, CLASS_9
from bot_template.config import get_local_time, MOSCOW_TZ
from bot_template.utils.formatting import (
    WEEKDAYS_RU, WEEKDAYS_RU_FULL,
    format_date_with_weekday, format_lesson_time,
    format_duration_short, format_duration_label,
    format_time_range, format_lesson_word,
)
import bot_template.app.keyboards as kb

from .common import (
    router, db, logger,
    AdminPanelStates,
    is_admin, check_admin_access, check_admin_access_callback,
    safe_callback_answer,
)

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

@router.callback_query(F.data.startswith("add_manual_lesson_"))
async def add_manual_lesson_start(callback: CallbackQuery, state: FSMContext):
    """Начать создание занятия вне расписания - показать календарь"""
    if not await check_admin_access_callback(callback):
        return

    try:
        student_id = int(callback.data.split("_")[3])
        student = await db.get_student(student_id)

        if not student:
            await callback.answer("❌ Ученик не найден", show_alert=True)
            return

        # Показываем календарь для выбора даты
        now = get_local_time()
        calendar_kb = kb.calendar_keyboard(
            year=now.year,
            month=now.month,
            context="cl",  # cl = create lesson
            extra_data=f"s{student_id}"
        )

        await callback.message.edit_text(
            f"➕ <b>ДОБАВЛЕНИЕ ЗАНЯТИЯ</b>\n\n"
            f"👤 Ученик: <b>{student['name']}</b>\n\n"
            f"📅 Выберите дату занятия:",
            reply_markup=calendar_kb,
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.message(AdminPanelStates.creating_lesson_date)
async def process_lesson_date(message: Message, state: FSMContext):
    """Обработка даты занятия"""
    if not await check_admin_access(message):
        await state.clear()
        return
    
    try:
        date_text = message.text.strip()
        
        # Пробуем разные форматы даты
        date_formats = ['%d.%m.%Y', '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']
        lesson_date = None
        
        for fmt in date_formats:
            try:
                lesson_date = datetime.strptime(date_text, fmt)
                break
            except ValueError:
                continue
        
        if not lesson_date:
            await message.answer(
                "❌ Неверный формат даты!\n\n"
                "Введите дату в формате ДД.ММ.ГГГГ (например: 25.12.2024):"
            )
            return
        
        # Проверяем, что дата не в прошлом
        if lesson_date.date() < get_local_time().date():
            await message.answer(
                "❌ Нельзя создавать занятие в прошлом!\n\n"
                "Введите актуальную или будущую дату:"
            )
            return
        
        lesson_date_str = lesson_date.strftime('%Y-%m-%d')
        
        await state.update_data(lesson_date=lesson_date_str)
        await state.set_state(AdminPanelStates.creating_lesson_time)
        
        await message.answer(
            f"✅ Дата: <b>{date_text}</b>\n\n"
            f"🕐 Введите время занятия в формате ЧЧ:ММ (например: 18:00):",
            parse_mode="HTML"
        )
        
    except Exception as e:
        await message.answer("❌ Ошибка при обработке даты. Попробуйте снова:")

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
    new_date_obj = datetime.strptime(new_date, '%Y-%m-%d')
    weekday = WEEKDAYS_RU[new_date_obj.weekday()]
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
    new_date_obj = datetime.strptime(new_date, '%Y-%m-%d')
    weekday = WEEKDAYS_RU[new_date_obj.weekday()]
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
    new_date_obj = datetime.strptime(new_date, '%Y-%m-%d')
    weekday = WEEKDAYS_RU[new_date_obj.weekday()]
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
        new_date_obj = datetime.strptime(new_date, '%Y-%m-%d')
        weekday = WEEKDAYS_RU[new_date_obj.weekday()]
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

    # Возвращаемся к списку занятий
    await callback.answer("❌ Перенос отменен")
    await callback.message.edit_text(
        "Перенос отменён",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ К списку занятий", callback_data=f"lessons_history_{student_id}")]
        ])
    )


# === РАЗДЕЛ "КАЛЕНДАРЬ" ===

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
            # Импортируем функцию из admin.py
            from .admin import show_student_card_internal
            await show_student_card_internal(callback, student_id, state)
        else:
            await callback.answer("❌ Ошибка возврата", show_alert=True)

    except Exception as e:
        logger.error(f"calendar_back error: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)
