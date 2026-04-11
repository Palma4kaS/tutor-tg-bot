from .common import (
    router, db, logger, kb,
    AdminPanelStates,
    is_admin, check_admin_access, check_admin_access_callback, safe_callback_answer,
    send_schedule_change_notification,
    DB_PATH,
    get_local_time,
    aiosqlite,
)
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import F, Bot
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
from bot_template.utils.formatting import format_date_with_weekday, format_lesson_time

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

