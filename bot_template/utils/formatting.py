"""
Общие утилиты форматирования дат, времени и текста.

Единый источник правды для функций, ранее продублированных
в handlers.py, keyboards.py, run.py и miniapp/backend/routers/student.py.
"""

from datetime import datetime, timedelta

# Словарь для русских названий дней недели (сокращённые)
WEEKDAYS_RU = {
    0: "Пн",
    1: "Вт",
    2: "Ср",
    3: "Чт",
    4: "Пт",
    5: "Сб",
    6: "Вс"
}

# Полные названия дней недели
WEEKDAYS_RU_FULL = [
    "Понедельник", "Вторник", "Среда", "Четверг",
    "Пятница", "Суббота", "Воскресенье"
]


def format_date_with_weekday(date_str: str, full_format: bool = False) -> str:
    """
    Форматирует дату с днём недели.

    Args:
        date_str: строка в формате 'YYYY-MM-DD'
        full_format: если True, возвращает 'ДД.ММ.ГГГГ (День)', иначе 'ДД.ММ (День)'
    """
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        weekday = WEEKDAYS_RU[date_obj.weekday()]

        if full_format:
            formatted_date = date_obj.strftime('%d.%m.%Y')
        else:
            formatted_date = date_obj.strftime('%d.%m')

        return f"{formatted_date} ({weekday})"
    except (ValueError, KeyError):
        return date_str


def format_lesson_time(lesson_time: str, duration: int = 60) -> str:
    """Форматирует время занятия с указанием времени окончания."""
    try:
        start_dt = datetime.strptime(lesson_time, '%H:%M')
        end_dt = start_dt + timedelta(minutes=duration)
        end_time = end_dt.strftime('%H:%M')

        duration_text = format_duration_short(duration)

        return f"{lesson_time}-{end_time}({duration_text})"
    except (ValueError, TypeError):
        duration_text = format_duration_short(duration)
        return f"{lesson_time}({duration_text})"


def format_duration_short(duration: int) -> str:
    """Короткий формат продолжительности: '1ч', '1.5ч', '2ч', '45м'."""
    try:
        duration = int(duration or 60)
    except (TypeError, ValueError):
        duration = 60

    if duration == 90:
        return "1.5ч"
    if duration >= 60:
        return f"{duration // 60}ч"
    return f"{duration}м"


def format_duration_label(duration: int) -> str:
    """Форматирует продолжительность в понятный текст: '60 мин'."""
    try:
        duration = int(duration or 60)
    except (TypeError, ValueError):
        duration = 60
    return f"{duration} мин"


def format_time_range(lesson_time: str, duration: int) -> str:
    """Возвращает диапазон времени занятия вида 'HH:MM – HH:MM'."""
    try:
        duration = int(duration or 60)
        start_dt = datetime.strptime(lesson_time, '%H:%M')
        end_dt = start_dt + timedelta(minutes=duration)
        return f"{lesson_time} – {end_dt.strftime('%H:%M')}"
    except (ValueError, TypeError):
        return lesson_time


def format_lesson_word(count: int) -> str:
    """Склоняет слово 'занятие' по числу."""
    try:
        count = abs(int(count))
    except (TypeError, ValueError):
        return "занятий"

    remainder_hundred = count % 100
    remainder_ten = count % 10

    if 11 <= remainder_hundred <= 14:
        return "занятий"
    if remainder_ten == 1:
        return "занятие"
    if 2 <= remainder_ten <= 4:
        return "занятия"
    return "занятий"
