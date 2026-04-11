"""Обработчики админ-панели: ученики, настройки, цены."""

from datetime import datetime, timedelta
from typing import Dict

from aiogram import F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

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
    AdminPanelStates, Reg,
    is_admin, check_admin_access, check_admin_access_callback,
    safe_callback_answer,
)

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
    
    # Сохраняем lesson_id и student_id в состояние
    await state.update_data(lesson_id=lesson_id, student_id=student_id)
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
# Обработчики фильтров перенесены в lessons.py (см. строки 1530-1578)

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

