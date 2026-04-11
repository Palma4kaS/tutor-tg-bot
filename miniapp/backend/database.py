import aiosqlite
from typing import Optional, List, Dict, AsyncGenerator
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import Depends

from config import DB_PATH, MOSCOW_TZ, get_db_path_for_tutor


def get_local_time() -> datetime:
    """Получить текущее московское время (UTC+3)"""
    return datetime.now(MOSCOW_TZ)


class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Контекстный менеджер для подключения к БД"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            yield db

    # === МЕТОДЫ ДЛЯ УЧЕНИКА ===

    async def get_student(self, user_id: int) -> Optional[Dict]:
        """Получить информацию об ученике"""
        async with self.get_connection() as db:
            async with db.execute(
                "SELECT * FROM students WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_lessons_by_student(self, user_id: int) -> List[Dict]:
        """Получить все занятия ученика"""
        async with self.get_connection() as db:
            async with db.execute(
                """SELECT * FROM lessons
                   WHERE student_id = ?
                   AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)
                   ORDER BY lesson_date DESC, lesson_time DESC""",
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_upcoming_lessons(self, user_id: int, days: int = 7) -> List[Dict]:
        """Получить предстоящие занятия на N дней вперёд"""
        today = get_local_time().strftime('%Y-%m-%d')
        future_date = (get_local_time() + timedelta(days=days)).strftime('%Y-%m-%d')

        async with self.get_connection() as db:
            async with db.execute(
                """SELECT * FROM lessons
                   WHERE student_id = ?
                   AND lesson_date >= ?
                   AND lesson_date <= ?
                   AND status = 'scheduled'
                   AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)
                   ORDER BY lesson_date ASC, lesson_time ASC""",
                (user_id, today, future_date)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_lessons_smart_filter(self, user_id: int) -> Dict[str, List[Dict]]:
        """
        Получить занятия с умной фильтрацией:
        - unpaid: все неоплаченные завершённые
        - upcoming: предстоящие на неделю вперёд
        - past: прошедшие за неделю (оплаченные)
        """
        today = get_local_time().strftime('%Y-%m-%d')
        week_ago = (get_local_time() - timedelta(days=7)).strftime('%Y-%m-%d')
        week_ahead = (get_local_time() + timedelta(days=7)).strftime('%Y-%m-%d')

        async with self.get_connection() as db:
            # Неоплаченные завершённые
            async with db.execute(
                """SELECT * FROM lessons
                   WHERE student_id = ?
                   AND status = 'completed'
                   AND payment_status = 'unpaid'
                   AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)
                   ORDER BY lesson_date DESC""",
                (user_id,)
            ) as cursor:
                unpaid = [dict(row) for row in await cursor.fetchall()]

            # Предстоящие
            async with db.execute(
                """SELECT * FROM lessons
                   WHERE student_id = ?
                   AND lesson_date >= ?
                   AND lesson_date <= ?
                   AND status = 'scheduled'
                   AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)
                   ORDER BY lesson_date ASC, lesson_time ASC""",
                (user_id, today, week_ahead)
            ) as cursor:
                upcoming = [dict(row) for row in await cursor.fetchall()]

            # Прошедшие (оплаченные)
            async with db.execute(
                """SELECT * FROM lessons
                   WHERE student_id = ?
                   AND lesson_date >= ?
                   AND lesson_date < ?
                   AND status = 'completed'
                   AND payment_status = 'paid'
                   AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)
                   ORDER BY lesson_date DESC""",
                (user_id, week_ago, today)
            ) as cursor:
                past = [dict(row) for row in await cursor.fetchall()]

        return {
            'unpaid': unpaid,
            'upcoming': upcoming,
            'past': past
        }

    async def get_student_homework_smart(self, user_id: int) -> Dict[str, List[Dict]]:
        """
        Получить ДЗ с умной фильтрацией:
        - active: прошлая неделя (7 дней назад до сегодня)
        - recent: следующая неделя (сегодня до +7 дней)
        """
        today = get_local_time().strftime('%Y-%m-%d')
        week_ago = (get_local_time() - timedelta(days=7)).strftime('%Y-%m-%d')
        week_ahead = (get_local_time() + timedelta(days=7)).strftime('%Y-%m-%d')

        async with self.get_connection() as db:
            # Прошлая неделя
            async with db.execute(
                """SELECT id, lesson_date, lesson_time, duration, homework,
                          homework_status, homework_photo_file_id, homework_file_id
                   FROM lessons
                   WHERE student_id = ?
                   AND lesson_date >= ?
                   AND lesson_date < ?
                   AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)
                   ORDER BY lesson_date DESC""",
                (user_id, week_ago, today)
            ) as cursor:
                active = [dict(row) for row in await cursor.fetchall()]

            # Следующая неделя
            async with db.execute(
                """SELECT id, lesson_date, lesson_time, duration, homework,
                          homework_status, homework_photo_file_id, homework_file_id
                   FROM lessons
                   WHERE student_id = ?
                   AND lesson_date >= ?
                   AND lesson_date <= ?
                   AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)
                   ORDER BY lesson_date ASC""",
                (user_id, today, week_ahead)
            ) as cursor:
                recent = [dict(row) for row in await cursor.fetchall()]

        return {
            'active': active,
            'recent': recent
        }

    async def get_lesson_by_id(self, lesson_id: int) -> Optional[Dict]:
        """Получить занятие по ID"""
        async with self.get_connection() as db:
            async with db.execute(
                """SELECT * FROM lessons
                   WHERE id = ?
                   AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)""",
                (lesson_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def can_change_parameter(self, user_id: int, change_type: str) -> tuple[bool, Optional[str]]:
        """
        Проверяет, можно ли изменить параметр (один раз в неделю).
        Возвращает (можно ли изменить, дата последнего изменения или None)
        """
        week_ago = (get_local_time() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')

        async with self.get_connection() as db:
            async with db.execute(
                """SELECT change_date
                   FROM student_changes_history
                   WHERE student_id = ? AND change_type = ? AND change_date >= ?
                   ORDER BY change_date DESC
                   LIMIT 1""",
                (user_id, change_type, week_ago)
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    return False, row[0]
                return True, None

    async def update_student_name(self, user_id: int, new_name: str) -> bool:
        """Обновить имя ученика"""
        today = get_local_time().strftime('%Y-%m-%d')
        now = get_local_time().strftime('%Y-%m-%d %H:%M:%S')

        async with self.get_connection() as db:
            # Получаем старое имя
            async with db.execute(
                "SELECT name FROM students WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                old_name = row[0] if row else None

            # Обновляем имя
            await db.execute(
                "UPDATE students SET name = ?, last_name_change_date = ? WHERE user_id = ?",
                (new_name, today, user_id)
            )

            # Записываем в историю
            if old_name and old_name != new_name:
                await db.execute(
                    """INSERT INTO student_changes_history
                       (student_id, change_type, old_value, new_value, change_date, changed_by)
                       VALUES (?, 'name', ?, ?, ?, 'student')""",
                    (user_id, old_name, new_name, now)
                )

            await db.commit()
        return True

    async def update_student_grade(self, user_id: int, new_grade: int) -> bool:
        """Обновить класс ученика"""
        today = get_local_time().strftime('%Y-%m-%d')
        now = get_local_time().strftime('%Y-%m-%d %H:%M:%S')

        async with self.get_connection() as db:
            # Получаем старый класс
            async with db.execute(
                "SELECT grade FROM students WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                old_grade = row[0] if row else None

            # Обновляем класс
            await db.execute(
                "UPDATE students SET grade = ?, last_grade_change_date = ? WHERE user_id = ?",
                (new_grade, today, user_id)
            )

            # Если класс < 10, убираем направление
            if new_grade < 10:
                await db.execute(
                    "UPDATE students SET subject = NULL WHERE user_id = ?",
                    (user_id,)
                )

            # Записываем в историю
            if old_grade is not None and old_grade != new_grade:
                await db.execute(
                    """INSERT INTO student_changes_history
                       (student_id, change_type, old_value, new_value, change_date, changed_by)
                       VALUES (?, 'grade', ?, ?, ?, 'student')""",
                    (user_id, str(old_grade), str(new_grade), now)
                )

            await db.commit()
        return True

    async def update_student_subject(self, user_id: int, new_subject: str) -> bool:
        """Обновить направление ученика (база/профиль)"""
        today = get_local_time().strftime('%Y-%m-%d')
        now = get_local_time().strftime('%Y-%m-%d %H:%M:%S')

        async with self.get_connection() as db:
            # Проверяем, что класс >= 10
            async with db.execute(
                "SELECT grade, subject FROM students WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row or row[0] < 10:
                    return False
                old_subject = row[1]

            # Обновляем направление
            await db.execute(
                "UPDATE students SET subject = ?, last_subject_change_date = ? WHERE user_id = ?",
                (new_subject, today, user_id)
            )

            # Записываем в историю
            if old_subject != new_subject:
                await db.execute(
                    """INSERT INTO student_changes_history
                       (student_id, change_type, old_value, new_value, change_date, changed_by)
                       VALUES (?, 'subject', ?, ?, ?, 'student')""",
                    (user_id, old_subject or '', new_subject, now)
                )

            await db.commit()
        return True


    # === МЕТОДЫ ДЛЯ УЧИТЕЛЯ ===

    async def get_all_students_with_debt(self) -> List[Dict]:
        """Получить всех учеников с суммой долга"""
        async with self.get_connection() as db:
            async with db.execute(
                """SELECT s.*,
                          COALESCE(SUM(CASE WHEN l.status = 'completed' AND l.payment_status = 'unpaid'
                                           AND (l.is_manually_deleted = 0 OR l.is_manually_deleted IS NULL)
                                      THEN l.price ELSE 0 END), 0) AS total_debt,
                          COUNT(CASE WHEN l.status = 'completed' AND l.payment_status = 'unpaid'
                                          AND (l.is_manually_deleted = 0 OR l.is_manually_deleted IS NULL)
                                     THEN 1 END) AS unpaid_lessons_count
                   FROM students s
                   LEFT JOIN lessons l ON l.student_id = s.user_id
                   GROUP BY s.user_id
                   ORDER BY s.name ASC"""
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_today_lessons_with_students(self) -> List[Dict]:
        """Получить занятия на сегодня с именами учеников"""
        today = get_local_time().strftime('%Y-%m-%d')
        async with self.get_connection() as db:
            async with db.execute(
                """SELECT l.*, s.name AS student_name
                   FROM lessons l
                   JOIN students s ON s.user_id = l.student_id
                   WHERE l.lesson_date = ?
                   AND (l.is_manually_deleted = 0 OR l.is_manually_deleted IS NULL)
                   ORDER BY l.lesson_time ASC""",
                (today,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_week_lessons_with_students(self) -> List[Dict]:
        """Получить занятия на ближайшие 7 дней с именами учеников"""
        today = get_local_time().strftime('%Y-%m-%d')
        week_ahead = (get_local_time() + timedelta(days=7)).strftime('%Y-%m-%d')
        async with self.get_connection() as db:
            async with db.execute(
                """SELECT l.*, s.name AS student_name
                   FROM lessons l
                   JOIN students s ON s.user_id = l.student_id
                   WHERE l.lesson_date >= ? AND l.lesson_date <= ?
                   AND (l.is_manually_deleted = 0 OR l.is_manually_deleted IS NULL)
                   ORDER BY l.lesson_date ASC, l.lesson_time ASC""",
                (today, week_ahead)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_debtors(self) -> List[Dict]:
        """Получить учеников с долгом"""
        async with self.get_connection() as db:
            async with db.execute(
                """SELECT s.*,
                          SUM(l.price) AS total_debt,
                          COUNT(l.id) AS unpaid_lessons_count
                   FROM students s
                   JOIN lessons l ON l.student_id = s.user_id
                   WHERE l.status = 'completed'
                   AND l.payment_status = 'unpaid'
                   AND (l.is_manually_deleted = 0 OR l.is_manually_deleted IS NULL)
                   GROUP BY s.user_id
                   HAVING total_debt > 0
                   ORDER BY total_debt DESC"""
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_new_students_count(self) -> int:
        """Получить количество новых (непросмотренных) учеников"""
        async with self.get_connection() as db:
            async with db.execute(
                "SELECT COUNT(*) FROM students WHERE viewed_by_teacher = 0 OR viewed_by_teacher IS NULL"
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def get_student_lessons_timeline(self, student_id: int) -> Dict:
        """
        Получить занятия ученика для таймлайна учителя:
        - upcoming: следующие 7 дней (запланированные)
        - recent: последние 14 дней (прошедшие)
        - has_more: есть ли занятия старше 14 дней
        """
        today = get_local_time().strftime('%Y-%m-%d')
        week_ahead = (get_local_time() + timedelta(days=7)).strftime('%Y-%m-%d')
        two_weeks_ago = (get_local_time() - timedelta(days=14)).strftime('%Y-%m-%d')

        async with self.get_connection() as db:
            # Предстоящие (следующие 7 дней, статус scheduled)
            async with db.execute(
                """SELECT * FROM lessons
                   WHERE student_id = ?
                   AND lesson_date >= ? AND lesson_date <= ?
                   AND status = 'scheduled'
                   AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)
                   ORDER BY lesson_date ASC, lesson_time ASC""",
                (student_id, today, week_ahead)
            ) as cursor:
                upcoming = [dict(row) for row in await cursor.fetchall()]

            # Прошедшие за 14 дней (все статусы, кроме scheduled в будущем)
            async with db.execute(
                """SELECT * FROM lessons
                   WHERE student_id = ?
                   AND lesson_date >= ? AND lesson_date < ?
                   AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)
                   ORDER BY lesson_date DESC, lesson_time DESC""",
                (student_id, two_weeks_ago, today)
            ) as cursor:
                recent = [dict(row) for row in await cursor.fetchall()]

            # Есть ли более старые занятия
            async with db.execute(
                """SELECT COUNT(*) FROM lessons
                   WHERE student_id = ?
                   AND lesson_date < ?
                   AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)""",
                (student_id, two_weeks_ago)
            ) as cursor:
                row = await cursor.fetchone()
                has_more = (row[0] > 0) if row else False

        return {'upcoming': upcoming, 'recent': recent, 'has_more': has_more}

    async def get_student_lessons_history(self, student_id: int, offset: int = 0, limit: int = 20) -> List[Dict]:
        """Получить старые занятия ученика (старше 14 дней) с пагинацией"""
        two_weeks_ago = (get_local_time() - timedelta(days=14)).strftime('%Y-%m-%d')
        async with self.get_connection() as db:
            async with db.execute(
                """SELECT * FROM lessons
                   WHERE student_id = ?
                   AND lesson_date < ?
                   AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)
                   ORDER BY lesson_date DESC, lesson_time DESC
                   LIMIT ? OFFSET ?""",
                (student_id, two_weeks_ago, limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_lesson_for_teacher(self, lesson_id: int) -> Optional[Dict]:
        """Получить занятие по ID для учителя"""
        async with self.get_connection() as db:
            async with db.execute(
                """SELECT l.*, s.name AS student_name
                   FROM lessons l
                   JOIN students s ON s.user_id = l.student_id
                   WHERE l.id = ?
                   AND (l.is_manually_deleted = 0 OR l.is_manually_deleted IS NULL)""",
                (lesson_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_lesson_payment(self, lesson_id: int, payment_status: str) -> bool:
        """Обновить статус оплаты занятия"""
        async with self.get_connection() as db:
            await db.execute(
                "UPDATE lessons SET payment_status = ? WHERE id = ?",
                (payment_status, lesson_id)
            )
            await db.commit()
        return True

    async def update_lesson_status(self, lesson_id: int, status: str) -> bool:
        """Обновить статус занятия"""
        async with self.get_connection() as db:
            await db.execute(
                "UPDATE lessons SET status = ? WHERE id = ?",
                (status, lesson_id)
            )
            await db.commit()
        return True

    async def update_lesson_homework(self, lesson_id: int, homework: str) -> bool:
        """Обновить домашнее задание занятия"""
        async with self.get_connection() as db:
            await db.execute(
                "UPDATE lessons SET homework = ? WHERE id = ?",
                (homework, lesson_id)
            )
            await db.commit()
        return True

    async def get_price_settings(self) -> Optional[Dict]:
        """Получить настройки цен"""
        async with self.get_connection() as db:
            async with db.execute(
                "SELECT * FROM price_settings ORDER BY id DESC LIMIT 1"
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def save_price_settings(self, base_price: float, online_surcharge: float,
                                  grade_9_surcharge: float, grade_10_11_surcharge: float,
                                  profile_surcharge: float) -> bool:
        """Сохранить настройки цен (обновить или создать)"""
        async with self.get_connection() as db:
            existing = await self.get_price_settings()
            if existing:
                await db.execute(
                    """UPDATE price_settings
                       SET base_price=?, online_surcharge=?, grade_9_surcharge=?,
                           grade_10_11_surcharge=?, profile_surcharge=?, updated_at=datetime('now')
                       WHERE id=?""",
                    (base_price, online_surcharge, grade_9_surcharge,
                     grade_10_11_surcharge, profile_surcharge, existing['id'])
                )
            else:
                await db.execute(
                    """INSERT INTO price_settings
                       (base_price, online_surcharge, grade_9_surcharge, grade_10_11_surcharge, profile_surcharge)
                       VALUES (?, ?, ?, ?, ?)""",
                    (base_price, online_surcharge, grade_9_surcharge,
                     grade_10_11_surcharge, profile_surcharge)
                )
            await db.commit()
            return True

    async def get_student_stats(self, student_id: int) -> Dict:
        """Получить статистику ученика (долг, количество занятий)"""
        async with self.get_connection() as db:
            async with db.execute(
                """SELECT
                       COALESCE(SUM(CASE WHEN status = 'completed' AND payment_status = 'unpaid'
                                         AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)
                                    THEN price ELSE 0 END), 0) AS total_debt,
                       COUNT(CASE WHEN status = 'completed' AND payment_status = 'unpaid'
                                       AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)
                                  THEN 1 END) AS unpaid_lessons_count,
                       COUNT(CASE WHEN (is_manually_deleted = 0 OR is_manually_deleted IS NULL)
                                  THEN 1 END) AS total_lessons_count
                   FROM lessons
                   WHERE student_id = ?""",
                (student_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else {'total_debt': 0, 'unpaid_lessons_count': 0, 'total_lessons_count': 0}


# Глобальный экземпляр базы данных (для обратной совместимости)
db = Database()


# Dependency для получения правильного экземпляра БД в multi-tenant режиме
def get_database_for_user(tutor_folder: str) -> Database:
    """
    Создаёт экземпляр БД для конкретного репетитора.

    Args:
        tutor_folder: Папка репетитора (например, 'tutor_910518469')

    Returns:
        Database: Экземпляр базы данных для этого репетитора
    """
    db_path = get_db_path_for_tutor(tutor_folder)
    return Database(db_path)
