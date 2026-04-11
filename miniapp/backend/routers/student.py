import os
import sys
from datetime import datetime, timedelta
import logging
from fastapi import APIRouter, Depends, HTTPException

# Добавляем корень проекта в sys.path для импорта из bot_template
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from bot_template.utils.formatting import format_date_with_weekday, format_time_range

from auth import TelegramUser, TelegramUserWithBot, get_current_user_with_bot
from database import Database, get_database_for_user
import httpx
from fastapi.responses import StreamingResponse
from schemas import (
    StudentProfile,
    Lesson,
    LessonsHistory,
    HomeworkItem,
    HomeworkList,
    HomeworkDetail,
    LessonDetail,
    FileUrlResponse,
    UpdateNameRequest,
    UpdateGradeRequest,
    UpdateSubjectRequest,
    UpdateProfileResponse
)

router = APIRouter(prefix="/student", tags=["student"])

# Настраиваем логирование
logger = logging.getLogger(__name__)


# Dependency для получения пользователя и БД
async def get_user_and_db(
    user_with_bot: TelegramUserWithBot = Depends(get_current_user_with_bot)
) -> tuple[TelegramUser, Database]:
    """Получить пользователя и соответствующую БД"""
    db = get_database_for_user(user_with_bot.tutor_folder)
    return user_with_bot.user, db


# Dependency для получения пользователя, БД и токена бота
async def get_user_db_and_token(
    user_with_bot: TelegramUserWithBot = Depends(get_current_user_with_bot)
) -> tuple[TelegramUser, Database, str]:
    """Получить пользователя, соответствующую БД и токен бота"""
    db = get_database_for_user(user_with_bot.tutor_folder)
    return user_with_bot.user, db, user_with_bot.bot_token


def lesson_to_schema(lesson: dict) -> Lesson:
    """Преобразует словарь занятия в Pydantic модель"""
    homework = lesson.get('homework') or ''
    has_homework = bool(homework.strip())
    duration = lesson.get('duration') or 60

    return Lesson(
        id=lesson['id'],
        lesson_date=lesson['lesson_date'],
        lesson_time=lesson['lesson_time'],
        duration=duration,
        price=lesson.get('price', 0),
        status=lesson.get('status', 'scheduled'),
        payment_status=lesson.get('payment_status', 'unpaid'),
        lesson_format=lesson.get('lesson_format'),
        homework=homework if has_homework else None,
        homework_status=lesson.get('homework_status'),
        has_homework=has_homework,
        time_range=format_time_range(lesson['lesson_time'], duration),
        formatted_date=format_date_with_weekday(lesson['lesson_date'])
    )


def homework_to_schema(lesson: dict) -> HomeworkItem:
    """Преобразует словарь занятия в HomeworkItem"""
    homework = lesson.get('homework') or ''
    has_homework = bool(homework.strip())
    duration = lesson.get('duration') or 60

    return HomeworkItem(
        id=lesson['id'],
        lesson_date=lesson['lesson_date'],
        lesson_time=lesson['lesson_time'],
        duration=duration,
        has_homework=has_homework,
        homework_status=lesson.get('homework_status'),
        formatted_date=format_date_with_weekday(lesson['lesson_date'])
    )


# === ЭНДПОИНТЫ ===

@router.get("/profile", response_model=StudentProfile)
async def get_profile(user_db: tuple[TelegramUser, Database] = Depends(get_user_and_db)):
    """Получить профиль ученика"""
    user, db = user_db
    logger.info(f"Profile request for user_id={user.id}, username={user.username}")

    student = await db.get_student(user.id)

    if not student:
        logger.warning(f"Student not found in database: user_id={user.id}")
        raise HTTPException(status_code=404, detail="Ученик не найден")

    logger.info(f"Student found: user_id={student['user_id']}, name={student['name']}")

    # Проверяем возможность изменения параметров
    can_change_name, last_name = await db.can_change_parameter(user.id, 'name')
    can_change_grade, last_grade = await db.can_change_parameter(user.id, 'grade')
    can_change_subject, last_subject = await db.can_change_parameter(user.id, 'subject')

    return StudentProfile(
        user_id=student['user_id'],
        name=student['name'],
        username=student.get('username'),
        phone=student['phone'],
        grade=student['grade'],
        subject=student.get('subject'),
        registration_date=student.get('registration_date'),
        can_change_name=can_change_name,
        can_change_grade=can_change_grade,
        can_change_subject=can_change_subject and student['grade'] >= 10,
        last_name_change=last_name,
        last_grade_change=last_grade,
        last_subject_change=last_subject
    )


@router.get("/lessons/upcoming", response_model=list[Lesson])
async def get_upcoming_lessons(user_db: tuple[TelegramUser, Database] = Depends(get_user_and_db)):
    """Получить предстоящие занятия (7 дней)"""
    user, db = user_db
    lessons = await db.get_upcoming_lessons(user.id, days=7)
    return [lesson_to_schema(lesson) for lesson in lessons[:10]]


@router.get("/lessons/history", response_model=LessonsHistory)
async def get_lessons_history(user_db: tuple[TelegramUser, Database] = Depends(get_user_and_db)):
    """Получить историю занятий с умной фильтрацией"""
    user, db = user_db
    data = await db.get_lessons_smart_filter(user.id)

    unpaid = [lesson_to_schema(l) for l in data['unpaid']]
    upcoming = [lesson_to_schema(l) for l in data['upcoming']]
    past = [lesson_to_schema(l) for l in data['past']]

    # Считаем общий долг
    total_debt = sum(l.price for l in unpaid)

    return LessonsHistory(
        unpaid=unpaid,
        upcoming=upcoming,
        past=past,
        total_debt=total_debt
    )


@router.get("/homework", response_model=HomeworkList)
async def get_homework_list(user_db: tuple[TelegramUser, Database] = Depends(get_user_and_db)):
    """Получить список ДЗ"""
    user, db = user_db
    data = await db.get_student_homework_smart(user.id)

    active = [homework_to_schema(l) for l in data['active']]
    recent = [homework_to_schema(l) for l in data['recent']]

    return HomeworkList(active=active, recent=recent)


@router.get("/homework/{lesson_id}", response_model=HomeworkDetail)
async def get_homework_detail(
    lesson_id: int,
    user_db: tuple[TelegramUser, Database] = Depends(get_user_and_db)
):
    """Получить детали ДЗ"""
    user, db = user_db
    lesson = await db.get_lesson_by_id(lesson_id)

    if not lesson:
        raise HTTPException(status_code=404, detail="Занятие не найдено")

    # Проверяем, что занятие принадлежит этому ученику
    if lesson['student_id'] != user.id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    duration = lesson.get('duration') or 60

    return HomeworkDetail(
        id=lesson['id'],
        lesson_date=lesson['lesson_date'],
        lesson_time=lesson['lesson_time'],
        duration=duration,
        homework=lesson.get('homework'),
        homework_status=lesson.get('homework_status'),
        homework_photo_file_id=lesson.get('homework_photo_file_id'),
        homework_file_id=lesson.get('homework_file_id'),
        homework_file_name=lesson.get('homework_file_name'),
        formatted_date=format_date_with_weekday(lesson['lesson_date'], full_format=True),
        time_range=format_time_range(lesson['lesson_time'], duration)
    )


@router.put("/profile/name", response_model=UpdateProfileResponse)
async def update_name(
    request: UpdateNameRequest,
    user_db: tuple[TelegramUser, Database] = Depends(get_user_and_db)
):
    """Изменить имя"""
    user, db = user_db
    # Проверяем, можно ли изменить
    can_change, last_change = await db.can_change_parameter(user.id, 'name')

    if not can_change:
        # Вычисляем, когда можно будет изменить
        if last_change:
            last_dt = datetime.strptime(last_change, '%Y-%m-%d %H:%M:%S')
            can_change_at = last_dt + timedelta(days=7)
            return UpdateProfileResponse(
                success=False,
                message="Имя можно изменять один раз в неделю",
                can_change_again=can_change_at.strftime('%d.%m.%Y')
            )

    # Обновляем имя
    await db.update_student_name(user.id, request.name)

    return UpdateProfileResponse(
        success=True,
        message="Имя успешно изменено"
    )


@router.put("/profile/grade", response_model=UpdateProfileResponse)
async def update_grade(
    request: UpdateGradeRequest,
    user_db: tuple[TelegramUser, Database] = Depends(get_user_and_db)
):
    """Изменить класс"""
    user, db = user_db
    # Проверяем, можно ли изменить
    can_change, last_change = await db.can_change_parameter(user.id, 'grade')

    if not can_change:
        if last_change:
            last_dt = datetime.strptime(last_change, '%Y-%m-%d %H:%M:%S')
            can_change_at = last_dt + timedelta(days=7)
            return UpdateProfileResponse(
                success=False,
                message="Класс можно изменять один раз в неделю",
                can_change_again=can_change_at.strftime('%d.%m.%Y')
            )

    # Обновляем класс
    await db.update_student_grade(user.id, request.grade)

    return UpdateProfileResponse(
        success=True,
        message="Класс успешно изменён"
    )


@router.put("/profile/subject", response_model=UpdateProfileResponse)
async def update_subject(
    request: UpdateSubjectRequest,
    user_db: tuple[TelegramUser, Database] = Depends(get_user_and_db)
):
    """Изменить направление (база/профиль)"""
    user, db = user_db
    # Проверяем класс ученика
    student = await db.get_student(user.id)
    if not student or student['grade'] < 10:
        raise HTTPException(
            status_code=400,
            detail="Направление доступно только для 10-11 классов"
        )

    # Проверяем, можно ли изменить
    can_change, last_change = await db.can_change_parameter(user.id, 'subject')

    if not can_change:
        if last_change:
            last_dt = datetime.strptime(last_change, '%Y-%m-%d %H:%M:%S')
            can_change_at = last_dt + timedelta(days=7)
            return UpdateProfileResponse(
                success=False,
                message="Направление можно изменять один раз в неделю",
                can_change_again=can_change_at.strftime('%d.%m.%Y')
            )

    # Нормализуем значение
    subject = request.subject.lower()
    if subject in ('base', 'база'):
        subject = 'база'
    elif subject in ('profile', 'профиль'):
        subject = 'профиль'

    # Обновляем направление
    await db.update_student_subject(user.id, subject)

    return UpdateProfileResponse(
        success=True,
        message="Направление успешно изменено"
    )


@router.get("/lessons/{lesson_id}", response_model=LessonDetail)
async def get_lesson_detail(
    lesson_id: int,
    user_db: tuple[TelegramUser, Database] = Depends(get_user_and_db)
):
    """Получить детальную информацию о занятии"""
    user, db = user_db
    lesson = await db.get_lesson_by_id(lesson_id)

    if not lesson:
        raise HTTPException(status_code=404, detail="Занятие не найдено")

    # Проверяем, что занятие принадлежит этому ученику
    if lesson['student_id'] != user.id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    duration = lesson.get('duration') or 60

    return LessonDetail(
        id=lesson['id'],
        lesson_date=lesson['lesson_date'],
        lesson_time=lesson['lesson_time'],
        duration=duration,
        price=lesson.get('price', 0),
        status=lesson.get('status', 'scheduled'),
        payment_status=lesson.get('payment_status', 'unpaid'),
        lesson_format=lesson.get('lesson_format'),
        homework=lesson.get('homework'),
        homework_status=lesson.get('homework_status'),
        homework_photo_file_id=lesson.get('homework_photo_file_id'),
        homework_file_id=lesson.get('homework_file_id'),
        homework_file_name=lesson.get('homework_file_name'),
        formatted_date=format_date_with_weekday(lesson['lesson_date'], full_format=True),
        time_range=format_time_range(lesson['lesson_time'], duration)
    )


async def get_telegram_file_url(bot_token: str, file_id: str) -> tuple[str, dict]:
    """Получить URL файла из Telegram"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.telegram.org/bot{bot_token}/getFile",
            params={"file_id": file_id}
        )
        data = response.json()

        if not data.get("ok"):
            raise HTTPException(status_code=404, detail="Файл не найден в Telegram")

        file_info = data["result"]
        file_path = file_info.get("file_path")
        if not file_path:
            raise HTTPException(status_code=404, detail="Не удалось получить путь к файлу")

        file_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        return file_url, file_info


@router.get("/file/{file_id}/proxy")
async def proxy_telegram_file(
    file_id: str,
    user_db_token: tuple[TelegramUser, Database, str] = Depends(get_user_db_and_token)
):
    """Проксировать файл из Telegram"""
    user, db, bot_token = user_db_token

    try:
        file_url, file_info = await get_telegram_file_url(bot_token, file_id)

        async def stream_file():
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", file_url) as response:
                    async for chunk in response.aiter_bytes():
                        yield chunk

        # Определяем content-type
        file_path = file_info.get("file_path", "")
        content_type = "application/octet-stream"
        if file_path.endswith((".jpg", ".jpeg")):
            content_type = "image/jpeg"
        elif file_path.endswith(".png"):
            content_type = "image/png"
        elif file_path.endswith(".gif"):
            content_type = "image/gif"
        elif file_path.endswith(".webp"):
            content_type = "image/webp"
        elif file_path.endswith(".pdf"):
            content_type = "application/pdf"
        elif file_path.endswith(".doc"):
            content_type = "application/msword"
        elif file_path.endswith(".docx"):
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        # Получаем имя файла
        file_name = file_path.split("/")[-1] if file_path else "file"

        return StreamingResponse(
            stream_file(),
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{file_name}"'
            }
        )
    except httpx.HTTPError as e:
        logger.error(f"Error fetching file from Telegram: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении файла")
