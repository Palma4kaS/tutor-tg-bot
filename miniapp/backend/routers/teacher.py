import os
import sys
import logging
from fastapi import APIRouter, Depends, HTTPException

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from bot_template.utils.formatting import format_date_with_weekday, format_time_range

from auth import TelegramUserWithBot, get_current_teacher
from database import Database, get_database_for_user
from schemas import (
    DashboardStats,
    TeacherLesson,
    TeacherLessonDetail,
    TeacherStudent,
    TeacherStudentDetail,
    TeacherStudentLessons,
    WeekSchedule,
    Lesson,
    PriceSettings,
    UpdatePriceSettingsRequest,
    UpdateLessonPaymentRequest,
    UpdateLessonStatusRequest,
    UpdateLessonHomeworkRequest,
)

router = APIRouter(prefix="/teacher", tags=["teacher"])
logger = logging.getLogger(__name__)


async def get_teacher_db(
    user_with_bot: TelegramUserWithBot = Depends(get_current_teacher)
) -> tuple[TelegramUserWithBot, Database]:
    db = get_database_for_user(user_with_bot.tutor_folder)
    return user_with_bot, db


def lesson_to_teacher_schema(lesson: dict) -> TeacherLesson:
    duration = lesson.get('duration') or 60
    homework = lesson.get('homework') or ''
    return TeacherLesson(
        id=lesson['id'],
        student_id=lesson['student_id'],
        student_name=lesson.get('student_name', ''),
        lesson_date=lesson['lesson_date'],
        lesson_time=lesson['lesson_time'],
        duration=duration,
        price=lesson.get('price', 0),
        status=lesson.get('status', 'scheduled'),
        payment_status=lesson.get('payment_status', 'unpaid'),
        lesson_format=lesson.get('lesson_format'),
        has_homework=bool(homework.strip()),
        time_range=format_time_range(lesson['lesson_time'], duration),
        formatted_date=format_date_with_weekday(lesson['lesson_date'])
    )


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard(
    teacher_db: tuple[TelegramUserWithBot, Database] = Depends(get_teacher_db)
):
    """Дашборд учителя: счётчики и занятия на сегодня"""
    _, db = teacher_db

    new_students_count = await db.get_new_students_count()
    debtors = await db.get_debtors()
    today_lessons_raw = await db.get_today_lessons_with_students()

    today_lessons = [lesson_to_teacher_schema(l) for l in today_lessons_raw]

    return DashboardStats(
        new_students_count=new_students_count,
        debtors_count=len(debtors),
        today_lessons_count=len(today_lessons),
        today_lessons=today_lessons
    )


@router.get("/schedule/week", response_model=WeekSchedule)
async def get_week_schedule(
    teacher_db: tuple[TelegramUserWithBot, Database] = Depends(get_teacher_db)
):
    """Расписание на ближайшие 7 дней, сгруппированное по датам"""
    _, db = teacher_db
    lessons_raw = await db.get_week_lessons_with_students()

    days: dict[str, list[TeacherLesson]] = {}
    for lesson in lessons_raw:
        date_key = lesson['lesson_date']
        if date_key not in days:
            days[date_key] = []
        days[date_key].append(lesson_to_teacher_schema(lesson))

    return WeekSchedule(days=days)


@router.get("/students", response_model=list[TeacherStudent])
async def get_students(
    teacher_db: tuple[TelegramUserWithBot, Database] = Depends(get_teacher_db)
):
    """Список всех учеников с суммой долга"""
    _, db = teacher_db
    students_raw = await db.get_all_students_with_debt()

    return [
        TeacherStudent(
            user_id=s['user_id'],
            name=s['name'],
            grade=s['grade'],
            subject=s.get('subject'),
            phone=s['phone'],
            registration_date=s.get('registration_date'),
            total_debt=s.get('total_debt', 0),
            unpaid_lessons_count=s.get('unpaid_lessons_count', 0),
            is_new=not bool(s.get('viewed_by_teacher', 0))
        )
        for s in students_raw
    ]


@router.get("/students/{student_id}", response_model=TeacherStudentDetail)
async def get_student_detail(
    student_id: int,
    teacher_db: tuple[TelegramUserWithBot, Database] = Depends(get_teacher_db)
):
    """Карточка ученика"""
    _, db = teacher_db

    student = await db.get_student(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Ученик не найден")

    stats = await db.get_student_stats(student_id)

    return TeacherStudentDetail(
        user_id=student['user_id'],
        name=student['name'],
        grade=student['grade'],
        subject=student.get('subject'),
        phone=student['phone'],
        registration_date=student.get('registration_date'),
        registration_format=student.get('registration_format'),
        total_debt=stats.get('total_debt', 0),
        unpaid_lessons_count=stats.get('unpaid_lessons_count', 0),
        total_lessons_count=stats.get('total_lessons_count', 0),
        is_new=not bool(student.get('viewed_by_teacher', 0))
    )


@router.get("/students/{student_id}/lessons", response_model=TeacherStudentLessons)
async def get_student_lessons(
    student_id: int,
    teacher_db: tuple[TelegramUserWithBot, Database] = Depends(get_teacher_db)
):
    """Таймлайн занятий ученика: ближайшая неделя + последние 14 дней"""
    _, db = teacher_db

    student = await db.get_student(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Ученик не найден")

    data = await db.get_student_lessons_timeline(student_id)

    def to_teacher_lesson(l: dict) -> TeacherLesson:
        duration = l.get('duration') or 60
        return TeacherLesson(
            id=l['id'],
            student_id=l['student_id'],
            student_name='',
            lesson_date=l['lesson_date'],
            lesson_time=l['lesson_time'],
            duration=duration,
            price=l.get('price', 0),
            status=l.get('status', 'scheduled'),
            payment_status=l.get('payment_status', 'unpaid'),
            lesson_format=l.get('lesson_format'),
            has_homework=bool((l.get('homework') or '').strip()),
            time_range=format_time_range(l['lesson_time'], duration),
            formatted_date=format_date_with_weekday(l['lesson_date'])
        )

    return TeacherStudentLessons(
        upcoming=[to_teacher_lesson(l) for l in data['upcoming']],
        recent=[to_teacher_lesson(l) for l in data['recent']],
        has_more=data['has_more']
    )


@router.get("/students/{student_id}/lessons/history", response_model=list[TeacherLesson])
async def get_student_lessons_history(
    student_id: int,
    offset: int = 0,
    limit: int = 20,
    teacher_db: tuple[TelegramUserWithBot, Database] = Depends(get_teacher_db)
):
    """Старые занятия ученика (старше 14 дней) с пагинацией"""
    _, db = teacher_db

    student = await db.get_student(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Ученик не найден")

    lessons_raw = await db.get_student_lessons_history(student_id, offset=offset, limit=limit)
    duration_default = 60

    return [
        TeacherLesson(
            id=l['id'],
            student_id=l['student_id'],
            student_name='',
            lesson_date=l['lesson_date'],
            lesson_time=l['lesson_time'],
            duration=l.get('duration') or duration_default,
            price=l.get('price', 0),
            status=l.get('status', 'scheduled'),
            payment_status=l.get('payment_status', 'unpaid'),
            lesson_format=l.get('lesson_format'),
            has_homework=bool((l.get('homework') or '').strip()),
            time_range=format_time_range(l['lesson_time'], l.get('duration') or duration_default),
            formatted_date=format_date_with_weekday(l['lesson_date'])
        )
        for l in lessons_raw
    ]


@router.get("/lessons/{lesson_id}", response_model=TeacherLessonDetail)
async def get_lesson_detail(
    lesson_id: int,
    teacher_db: tuple[TelegramUserWithBot, Database] = Depends(get_teacher_db)
):
    """Детали занятия для учителя"""
    _, db = teacher_db

    lesson = await db.get_lesson_for_teacher(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Занятие не найдено")

    duration = lesson.get('duration') or 60
    return TeacherLessonDetail(
        id=lesson['id'],
        student_id=lesson['student_id'],
        student_name=lesson.get('student_name', ''),
        lesson_date=lesson['lesson_date'],
        lesson_time=lesson['lesson_time'],
        duration=duration,
        price=lesson.get('price', 0),
        status=lesson.get('status', 'scheduled'),
        payment_status=lesson.get('payment_status', 'unpaid'),
        lesson_format=lesson.get('lesson_format'),
        homework=lesson.get('homework') or None,
        homework_status=lesson.get('homework_status'),
        time_range=format_time_range(lesson['lesson_time'], duration),
        formatted_date=format_date_with_weekday(lesson['lesson_date'])
    )


@router.patch("/lessons/{lesson_id}/payment", response_model=TeacherLessonDetail)
async def update_lesson_payment(
    lesson_id: int,
    request: UpdateLessonPaymentRequest,
    teacher_db: tuple[TelegramUserWithBot, Database] = Depends(get_teacher_db)
):
    """Обновить статус оплаты занятия"""
    _, db = teacher_db

    lesson = await db.get_lesson_for_teacher(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Занятие не найдено")

    await db.update_lesson_payment(lesson_id, request.payment_status)
    updated = await db.get_lesson_for_teacher(lesson_id)
    duration = updated.get('duration') or 60
    return TeacherLessonDetail(
        id=updated['id'],
        student_id=updated['student_id'],
        student_name=updated.get('student_name', ''),
        lesson_date=updated['lesson_date'],
        lesson_time=updated['lesson_time'],
        duration=duration,
        price=updated.get('price', 0),
        status=updated.get('status', 'scheduled'),
        payment_status=updated.get('payment_status', 'unpaid'),
        lesson_format=updated.get('lesson_format'),
        homework=updated.get('homework') or None,
        homework_status=updated.get('homework_status'),
        time_range=format_time_range(updated['lesson_time'], duration),
        formatted_date=format_date_with_weekday(updated['lesson_date'])
    )


@router.patch("/lessons/{lesson_id}/status", response_model=TeacherLessonDetail)
async def update_lesson_status(
    lesson_id: int,
    request: UpdateLessonStatusRequest,
    teacher_db: tuple[TelegramUserWithBot, Database] = Depends(get_teacher_db)
):
    """Обновить статус занятия"""
    _, db = teacher_db

    lesson = await db.get_lesson_for_teacher(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Занятие не найдено")

    await db.update_lesson_status(lesson_id, request.status)
    updated = await db.get_lesson_for_teacher(lesson_id)
    duration = updated.get('duration') or 60
    return TeacherLessonDetail(
        id=updated['id'],
        student_id=updated['student_id'],
        student_name=updated.get('student_name', ''),
        lesson_date=updated['lesson_date'],
        lesson_time=updated['lesson_time'],
        duration=duration,
        price=updated.get('price', 0),
        status=updated.get('status', 'scheduled'),
        payment_status=updated.get('payment_status', 'unpaid'),
        lesson_format=updated.get('lesson_format'),
        homework=updated.get('homework') or None,
        homework_status=updated.get('homework_status'),
        time_range=format_time_range(updated['lesson_time'], duration),
        formatted_date=format_date_with_weekday(updated['lesson_date'])
    )


@router.patch("/lessons/{lesson_id}/homework", response_model=TeacherLessonDetail)
async def update_lesson_homework(
    lesson_id: int,
    request: UpdateLessonHomeworkRequest,
    teacher_db: tuple[TelegramUserWithBot, Database] = Depends(get_teacher_db)
):
    """Обновить домашнее задание занятия"""
    _, db = teacher_db

    lesson = await db.get_lesson_for_teacher(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Занятие не найдено")

    await db.update_lesson_homework(lesson_id, request.homework)
    updated = await db.get_lesson_for_teacher(lesson_id)
    duration = updated.get('duration') or 60
    return TeacherLessonDetail(
        id=updated['id'],
        student_id=updated['student_id'],
        student_name=updated.get('student_name', ''),
        lesson_date=updated['lesson_date'],
        lesson_time=updated['lesson_time'],
        duration=duration,
        price=updated.get('price', 0),
        status=updated.get('status', 'scheduled'),
        payment_status=updated.get('payment_status', 'unpaid'),
        lesson_format=updated.get('lesson_format'),
        homework=updated.get('homework') or None,
        homework_status=updated.get('homework_status'),
        time_range=format_time_range(updated['lesson_time'], duration),
        formatted_date=format_date_with_weekday(updated['lesson_date'])
    )


@router.get("/settings", response_model=PriceSettings)
async def get_settings(
    teacher_db: tuple[TelegramUserWithBot, Database] = Depends(get_teacher_db)
):
    """Получить настройки цен"""
    _, db = teacher_db
    settings = await db.get_price_settings()
    if not settings:
        return PriceSettings()
    return PriceSettings(
        base_price=settings['base_price'],
        online_surcharge=settings['online_surcharge'],
        grade_9_surcharge=settings['grade_9_surcharge'],
        grade_10_11_surcharge=settings['grade_10_11_surcharge'],
        profile_surcharge=settings['profile_surcharge'],
        updated_at=settings.get('updated_at')
    )


@router.put("/settings", response_model=PriceSettings)
async def update_settings(
    request: UpdatePriceSettingsRequest,
    teacher_db: tuple[TelegramUserWithBot, Database] = Depends(get_teacher_db)
):
    """Обновить настройки цен"""
    _, db = teacher_db
    await db.save_price_settings(
        base_price=request.base_price,
        online_surcharge=request.online_surcharge,
        grade_9_surcharge=request.grade_9_surcharge,
        grade_10_11_surcharge=request.grade_10_11_surcharge,
        profile_surcharge=request.profile_surcharge
    )
    settings = await db.get_price_settings()
    return PriceSettings(
        base_price=settings['base_price'],
        online_surcharge=settings['online_surcharge'],
        grade_9_surcharge=settings['grade_9_surcharge'],
        grade_10_11_surcharge=settings['grade_10_11_surcharge'],
        profile_surcharge=settings['profile_surcharge'],
        updated_at=settings.get('updated_at')
    )


@router.get("/debtors", response_model=list[TeacherStudent])
async def get_debtors(
    teacher_db: tuple[TelegramUserWithBot, Database] = Depends(get_teacher_db)
):
    """Список должников"""
    _, db = teacher_db
    debtors_raw = await db.get_debtors()

    return [
        TeacherStudent(
            user_id=s['user_id'],
            name=s['name'],
            grade=s['grade'],
            subject=s.get('subject'),
            phone=s['phone'],
            registration_date=s.get('registration_date'),
            total_debt=s.get('total_debt', 0),
            unpaid_lessons_count=s.get('unpaid_lessons_count', 0),
            is_new=not bool(s.get('viewed_by_teacher', 0))
        )
        for s in debtors_raw
    ]
