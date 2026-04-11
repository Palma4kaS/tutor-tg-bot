"""Обработчики домашних заданий: добавление, редактирование, вложения."""

from datetime import datetime, timedelta
from typing import Dict

from aiogram import F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from config import ADMINS_IDS, TUTOR_ID, DB_PATH
from bot_template.config import get_local_time, MOSCOW_TZ
from bot_template.utils.formatting import format_date_with_weekday
import bot_template.app.keyboards as kb

from .common import (
    router, db, logger,
    AdminPanelStates,
    is_admin, check_admin_access_callback,
    safe_callback_answer,
)

from .lessons import update_lesson_payment_message


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

        if is_editing:
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

        if is_editing:
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
            await message.answer(
                f"✅ Домашнее задание сохранено с фото:\n\n{homework_text}",
                reply_markup=kb.homework_navigation_keyboard(student_id) if is_editing else kb.lesson_ending_keyboard(source_lesson_id, source_student_id)
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
                await message.answer(
                    f"✅ Домашнее задание сохранено с фото и файлом:\n\n{homework_text}",
                    reply_markup=kb.homework_navigation_keyboard(student_id) if is_editing else kb.lesson_ending_keyboard(source_lesson_id, source_student_id)
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
            await message.answer(
                f"✅ Домашнее задание сохранено с файлом:\n\n{homework_text}",
                reply_markup=kb.homework_navigation_keyboard(student_id) if is_editing else kb.lesson_ending_keyboard(source_lesson_id, source_student_id)
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
                await message.answer(
                    f"✅ Домашнее задание сохранено с фото и файлом:\n\n{homework_text}",
                    reply_markup=kb.homework_navigation_keyboard(student_id) if is_editing else kb.lesson_ending_keyboard(source_lesson_id, source_student_id)
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

@router.callback_query(F.data.startswith("homework_added_"))
async def homework_added_confirmation(callback: CallbackQuery):
    """Подтверждение добавления ДЗ - возврат к занятию"""
    lesson_id = int(callback.data.split("_")[-1])
    await callback.answer("✅ ДЗ добавлено")
