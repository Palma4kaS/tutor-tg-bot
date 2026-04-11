"""Обработчики для ученика: регистрация, профиль, расписание, уроки, ДЗ."""

from datetime import datetime, timedelta
from typing import Dict

from aiogram import F, Bot
from aiogram.filters import Command
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
    is_admin, check_admin_access,
    safe_callback_answer,
)


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
