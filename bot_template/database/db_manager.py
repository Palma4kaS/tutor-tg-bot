import aiosqlite
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timedelta

from bot_template.utils.logger import get_logger

# Logger для этого модуля
logger = get_logger("database")

# Импортируем функцию для получения локального времени и часовой пояс
try:
    from bot_template.config import get_local_time, MOSCOW_TZ
except ImportError:
    # Если импорт не удался, используем datetime.now() как fallback
    from datetime import timezone, timedelta
    MOSCOW_TZ = timezone(timedelta(hours=3))
    def get_local_time():
        return datetime.now(MOSCOW_TZ)

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path

    async def init_db(self):
        """Инициализация БД с автоматической синхронизацией структуры"""
        async with aiosqlite.connect(self.db_path) as db:
            logger.info("Проверяем и обновляем структуру базы данных...")

            # 1. Создаем основные таблицы (если их нет)
            await self._ensure_tables_exist(db)

            # 2. Добавляем недостающие колонки
            await self._ensure_columns_exist(db)

            # 3. Создаем индексы (после того, как все колонки существуют)
            await self._ensure_indices_exist(db)

            await db.commit()
            logger.info("Структура базы данных актуальна")

    async def _ensure_tables_exist(self, db):
        """Создает таблицы, если их нет"""
        
        # Таблица students
        await db.execute("""
            CREATE TABLE IF NOT EXISTS students (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                username TEXT,
                phone TEXT NOT NULL,
                grade INTEGER,
                subject TEXT,
                registration_date DATE DEFAULT (date('now'))
            )
        """)
        
        # Таблица lessons (базовая структура)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                lesson_date TEXT NOT NULL,
                lesson_time TEXT NOT NULL,
                subject TEXT,
                lesson_format TEXT,
                price REAL,
                status TEXT DEFAULT 'scheduled',
                created_date DATE DEFAULT (date('now')),
                FOREIGN KEY (student_id) REFERENCES students(user_id)
            )
        """)
        
        # Таблица schedules
        await db.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                weekday INTEGER NOT NULL,
                time TEXT NOT NULL,
                lesson_format TEXT NOT NULL,
                price REAL NOT NULL,
                subject TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (student_id) REFERENCES students(user_id)
            )
        """)
        
        # Таблица истории изменений учеников
        await db.execute("""
            CREATE TABLE IF NOT EXISTS student_changes_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                change_type TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                change_date TEXT DEFAULT (datetime('now')),
                changed_by TEXT DEFAULT 'student',
                FOREIGN KEY (student_id) REFERENCES students(user_id)
            )
        """)
        
        # Таблица настроек цен
        await db.execute("""
            CREATE TABLE IF NOT EXISTS price_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base_price REAL NOT NULL DEFAULT 1000,
                online_surcharge REAL NOT NULL DEFAULT 0,
                grade_9_surcharge REAL NOT NULL DEFAULT 0,
                grade_10_11_surcharge REAL NOT NULL DEFAULT 0,
                profile_surcharge REAL NOT NULL DEFAULT 0,
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        
        # Таблица запланированных задач
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_id INTEGER,
                task_type TEXT NOT NULL,
                scheduled_time TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                execution_data TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                created_at TEXT DEFAULT (datetime('now')),
                executed_at TEXT,
                error_message TEXT,
                FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE CASCADE
            )
        """)

    async def _ensure_columns_exist(self, db):
        """Добавляет недостающие колонки в существующие таблицы"""
        
        # Новые колонки для таблицы lessons
        new_columns = [
            ("schedule_id", "INTEGER DEFAULT NULL"),
            ("is_rescheduled", "BOOLEAN DEFAULT 0"),
            ("original_date", "TEXT DEFAULT NULL"),
            ("notes", "TEXT DEFAULT NULL"),
            # НОВЫЕ ПОЛЯ:
            ("payment_status", "TEXT DEFAULT 'unpaid'"),  # paid, unpaid, pending
            ("homework", "TEXT DEFAULT NULL"),
            ("homework_status", "TEXT DEFAULT NULL"),  # assigned, completed, not_done
            ("homework_photo_file_id", "TEXT DEFAULT NULL"),  # file_id фото для ДЗ
            ("homework_file_id", "TEXT DEFAULT NULL"),  # file_id файла для ДЗ
            ("duration", "INTEGER DEFAULT 60"),  # продолжительность в минутах
            ("confirmation_status", "TEXT DEFAULT NULL"),  # confirmed, not_confirmed, NULL (не отправлено)
            ("confirmation_sent_at", "TEXT DEFAULT NULL"),  # когда отправлено уведомление с кнопкой подтверждения
            ("ending_notification_sent_at", "TEXT DEFAULT NULL"),  # когда отправлено уведомление об окончании за 5 минут
            ("start_notification_sent_at", "TEXT DEFAULT NULL"),  # когда отправлено уведомление о начале занятия
            ("is_manually_deleted", "BOOLEAN DEFAULT 0")  # флаг ручного удаления (мягкое удаление)
        ]
        
        for column_name, column_definition in new_columns:
            if not await self._column_exists(db, 'lessons', column_name):
                try:
                    await db.execute(f"ALTER TABLE lessons ADD COLUMN {column_name} {column_definition}")
                    logger.info(f"Добавлена колонка lessons.{column_name}")
                except Exception as e:
                    logger.error(f"Ошибка добавления lessons.{column_name}: {e}")
        # Новые колонки для таблицы schedules  
        schedules_columns = [
            ("duration", "INTEGER DEFAULT 60")  # продолжительность в минутах
        ]

        for column_name, column_definition in schedules_columns:
            if not await self._column_exists(db, 'schedules', column_name):
                try:
                    await db.execute(f"ALTER TABLE schedules ADD COLUMN {column_name} {column_definition}")
                    logger.info(f"Добавлена колонка schedules.{column_name}")
                except Exception as e:
                    logger.error(f"Ошибка добавления schedules.{column_name}: {e}")
        
        # Новые колонки для таблицы students (отслеживание дат изменений)
        students_columns = [
            ("last_name_change_date", "TEXT DEFAULT NULL"),  # Дата последнего изменения имени
            ("last_grade_change_date", "TEXT DEFAULT NULL"),  # Дата последнего изменения класса
            ("last_subject_change_date", "TEXT DEFAULT NULL"),  # Дата последнего изменения направления
            ("viewed_by_teacher", "BOOLEAN DEFAULT 0"),  # Флаг, был ли ученик просмотрен учителем
            ("registration_format", "TEXT DEFAULT NULL"),  # Формат регистрации (online/offline)
            ("registration_price", "REAL DEFAULT NULL"),  # Цена указанная при регистрации
            ("registration_feedback", "TEXT DEFAULT NULL"),  # Откуда узнали о репетиторе
            ("telegram_full_name", "TEXT DEFAULT NULL"),  # Полное имя из Telegram
            ("custom_price_per_hour", "REAL DEFAULT NULL")  # Индивидуальная цена за час для ученика
        ]
        
        for column_name, column_definition in students_columns:
            if not await self._column_exists(db, 'students', column_name):
                try:
                    await db.execute(f"ALTER TABLE students ADD COLUMN {column_name} {column_definition}")
                    logger.info(f"Добавлена колонка students.{column_name}")
                except Exception as e:
                    logger.error(f"Ошибка добавления students.{column_name}: {e}")

    async def _ensure_indices_exist(self, db):
        """Создает индексы для оптимизации запросов (вызывается после добавления всех колонок)"""

        # Индексы для таблицы scheduled_tasks
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_status_time
            ON scheduled_tasks(status, scheduled_time)
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_lesson_type
            ON scheduled_tasks(lesson_id, task_type, status)
        """)

        # Индексы для таблицы lessons (критично для производительности)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_lessons_student_date
            ON lessons(student_id, lesson_date)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_lessons_student_status
            ON lessons(student_id, status)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_lessons_date_status
            ON lessons(lesson_date, status)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_lessons_payment_status
            ON lessons(payment_status, status)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_lessons_schedule_id
            ON lessons(schedule_id)
        """)

        # Индексы для таблицы students
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_students_viewed
            ON students(viewed_by_teacher)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_students_registration
            ON students(registration_date)
        """)

        # Индексы для таблицы student_changes_history
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_changes_student_date
            ON student_changes_history(student_id, change_date)
        """)

        # Индексы для таблицы schedules
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_schedules_student_active
            ON schedules(student_id, is_active)
        """)

        logger.info("Индексы созданы/обновлены")

    async def _column_exists(self, db, table_name: str, column_name: str) -> bool:
        """Проверяет, существует ли колонка в таблице"""
        cursor = await db.execute(f"PRAGMA table_info({table_name})")
        columns = await cursor.fetchall()
        column_names = [column[1] for column in columns]  # column[1] = имя колонки
        return column_name in column_names

    # === МЕТОДЫ ДЛЯ РАБОТЫ С УЧЕНИКАМИ ===
    
    async def add_student(self, user_id: int, name: str, username: str, phone: str, 
                         grade: int, subject: str, registration_format: str = None,
                         registration_price: float = None, registration_feedback: str = None,
                         telegram_full_name: str = None):
        """Добавить нового ученика"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO students 
                (user_id, name, username, phone, grade, subject, registration_format, 
                 registration_price, registration_feedback, telegram_full_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, name, username, phone, grade, subject, registration_format,
                  registration_price, registration_feedback, telegram_full_name))
            await db.commit()

    async def get_student(self, user_id: int) -> Optional[Dict]:
        """Получить информацию об ученике"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM students WHERE user_id = ?", 
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def search_student_by_name(self, name: str) -> List[Dict]:
        """Поиск ученика по имени (частичное совпадение)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM students WHERE name LIKE ? ORDER BY name",
                (f"%{name}%",)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def search_student_by_username(self, username: str) -> Optional[Dict]:        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM students WHERE username = ?",
                (username,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_student_count(self) -> int:
        """Получить количество учеников"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM students") as cursor:
                result = await cursor.fetchone()
                return result[0]

    async def get_all_students(self) -> List[Dict]:
        """Получить всех учеников"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM students") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_new_students(self) -> List[Dict]:
        """Получить только новых (непросмотренных) учеников, отсортированных по дате регистрации"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT * FROM students 
                   WHERE viewed_by_teacher = 0 OR viewed_by_teacher IS NULL
                   ORDER BY registration_date ASC"""
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def mark_student_viewed(self, user_id: int) -> bool:
        """Пометить ученика как просмотренного учителем"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE students SET viewed_by_teacher = 1 WHERE user_id = ?",
                (user_id,)
            )
            await db.commit()
            return cursor.rowcount > 0
    
    async def can_change_parameter(self, user_id: int, change_type: str) -> Tuple[bool, Optional[str]]:
        """Проверяет, можно ли изменить параметр (один раз в неделю). 
        Возвращает (можно ли изменить, дата последнего изменения или None)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            week_ago = (get_local_time() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            
            # Проверяем в истории изменений
            cursor = await db.execute("""
                SELECT change_date 
                FROM student_changes_history 
                WHERE student_id = ? AND change_type = ? AND change_date >= ?
                ORDER BY change_date DESC
                LIMIT 1
            """, (user_id, change_type, week_ago))
            
            row = await cursor.fetchone()
            
            if row and row[0]:
                # Было изменение на этой неделе
                return False, row[0]
            
            return True, None
    
    async def can_send_change_notification(self, user_id: int, change_type: str) -> bool:
        """Проверяет, можно ли отправить уведомление об изменении (не было изменений сегодня)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            today = get_local_time().strftime('%Y-%m-%d')
            
            column_map = {
                'name': 'last_name_change_date',
                'grade': 'last_grade_change_date',
                'subject': 'last_subject_change_date'
            }
            
            column_name = column_map.get(change_type)
            if not column_name:
                return True  # Если тип неизвестен, разрешаем отправку
            
            cursor = await db.execute(
                f"SELECT {column_name} FROM students WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if not row or not row[0]:
                return True  # Если дата не установлена, можно отправить
            
            last_change_date = row[0]
            return last_change_date != today
    
    async def update_student_name(self, user_id: int, new_name: str, update_date: bool = True, changed_by: str = 'student') -> Tuple[bool, bool]:
        """Обновить имя ученика. 
        Возвращает (успешно ли обновлено, нужно ли отправить уведомление)"""
        today = get_local_time().strftime('%Y-%m-%d')
        can_notify = await self.can_send_change_notification(user_id, 'name')
        
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем старое значение перед обновлением
            cursor = await db.execute("SELECT name FROM students WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            old_name = row[0] if row else None
            
            if update_date and can_notify:
                await db.execute(
                    "UPDATE students SET name = ?, last_name_change_date = ? WHERE user_id = ?",
                    (new_name, today, user_id)
                )
                # Сохраняем в историю, если значение изменилось
                if old_name and old_name != new_name:
                    await db.execute(
                        """INSERT INTO student_changes_history 
                           (student_id, change_type, old_value, new_value, change_date, changed_by)
                           VALUES (?, 'name', ?, ?, ?, ?)""",
                        (user_id, old_name, new_name, get_local_time().strftime('%Y-%m-%d %H:%M:%S'), changed_by)
                    )
            else:
                await db.execute(
                    "UPDATE students SET name = ? WHERE user_id = ?",
                    (new_name, user_id)
                )
                # Сохраняем в историю даже если не нужно уведомление
                if old_name and old_name != new_name:
                    await db.execute(
                        """INSERT INTO student_changes_history 
                           (student_id, change_type, old_value, new_value, change_date, changed_by)
                           VALUES (?, 'name', ?, ?, ?, ?)""",
                        (user_id, old_name, new_name, get_local_time().strftime('%Y-%m-%d %H:%M:%S'), changed_by)
                    )
            await db.commit()
        
        return True, can_notify

    async def update_student_grade(self, user_id: int, new_grade: int, update_date: bool = True, changed_by: str = 'student') -> bool:
        """Обновить класс ученика. Возвращает True, если нужно отправить уведомление"""
        today = get_local_time().strftime('%Y-%m-%d')
        can_notify = await self.can_send_change_notification(user_id, 'grade')
        
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем старое значение перед обновлением
            cursor = await db.execute("SELECT grade FROM students WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            old_grade = row[0] if row and row[0] else None
            
            if update_date and can_notify:
                await db.execute(
                    "UPDATE students SET grade = ?, last_grade_change_date = ? WHERE user_id = ?",
                    (new_grade, today, user_id)
                )
                # Сохраняем в историю, если значение изменилось
                if old_grade is not None and old_grade != new_grade:
                    await db.execute(
                        """INSERT INTO student_changes_history 
                           (student_id, change_type, old_value, new_value, change_date, changed_by)
                           VALUES (?, 'grade', ?, ?, ?, ?)""",
                        (user_id, str(old_grade), str(new_grade), get_local_time().strftime('%Y-%m-%d %H:%M:%S'), changed_by)
                    )
            else:
                await db.execute(
                    "UPDATE students SET grade = ? WHERE user_id = ?",
                    (new_grade, user_id)
                )
                # Сохраняем в историю даже если не нужно уведомление
                if old_grade is not None and old_grade != new_grade:
                    await db.execute(
                        """INSERT INTO student_changes_history 
                           (student_id, change_type, old_value, new_value, change_date, changed_by)
                           VALUES (?, 'grade', ?, ?, ?, ?)""",
                        (user_id, str(old_grade), str(new_grade), get_local_time().strftime('%Y-%m-%d %H:%M:%S'), changed_by)
                    )
            await db.commit()
        
        return can_notify

    async def update_student_grade_with_subject(self, user_id: int, new_grade: int, new_subject: str = None):
        """Обновить класс ученика и направление (если нужно)"""
        async with aiosqlite.connect(self.db_path) as db:
            if new_grade < 9:
                # Если класс меньше 9 — убираем направление
                await db.execute(
                    "UPDATE students SET grade = ?, subject = NULL WHERE user_id = ?",
                    (new_grade, user_id)
                )
            else:
                # Если класс 9+ — обновляем направление
                await db.execute(
                    "UPDATE students SET grade = ?, subject = ? WHERE user_id = ?",
                    (new_grade, new_subject, user_id)
                )
            await db.commit()

    async def add_lesson(self, student_id: int, lesson_date: str, 
                        lesson_time: str, subject: str, 
                        lesson_format: str, price: float, duration: int = 60):
        """Добавить новое занятие"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO lessons (student_id, lesson_date, lesson_time, 
                                   subject, lesson_format, price, duration, status, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'scheduled', date('now'))
            """, (student_id, lesson_date, lesson_time, subject, 
                  lesson_format, price, duration))
            await db.commit()
            cursor = await db.execute("SELECT last_insert_rowid()")
            result = await cursor.fetchone()
            return result[0] if result else None

    async def get_lessons_by_student(self, student_id: int) -> List[Dict]:
        """Получить все занятия ученика (исключая мягко удаленные)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM lessons WHERE student_id = ? AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL) ORDER BY lesson_date",
                (student_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_all_lessons(self) -> List[Dict]:
        """Получить все занятия (исключая мягко удаленные)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT l.*, s.name as student_name 
                FROM lessons l 
                JOIN students s ON l.student_id = s.user_id 
                WHERE (l.is_manually_deleted = 0 OR l.is_manually_deleted IS NULL)
                ORDER BY l.lesson_date, l.lesson_time
            """) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_student_lessons_stats(self, student_id: int) -> Dict:
        """Получить статистику занятий ученика (месяц/полгода/год)
        
        Считаются только оплаченные занятия (payment_status = 'paid')
        """
        now = get_local_time()
        
        # Даты для периодов
        month_ago = now - timedelta(days=30)
        half_year_ago = now - timedelta(days=180)
        year_ago = now - timedelta(days=365)
        
        async with aiosqlite.connect(self.db_path) as db:
            # За месяц (только оплаченные)
            async with db.execute(
                """SELECT COUNT(*), COALESCE(SUM(price), 0) 
                FROM lessons 
                WHERE student_id = ? 
                AND lesson_date >= ?
                AND payment_status = 'paid'
                AND status = 'completed'
                AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)""",
                (student_id, month_ago.strftime('%Y-%m-%d'))
            ) as cursor:
                month_count, month_sum = await cursor.fetchone()
            
            # За полгода (только оплаченные)
            async with db.execute(
                """SELECT COUNT(*), COALESCE(SUM(price), 0) 
                FROM lessons 
                WHERE student_id = ? 
                AND lesson_date >= ?
                AND payment_status = 'paid'
                AND status = 'completed'
                AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)""",
                (student_id, half_year_ago.strftime('%Y-%m-%d'))
            ) as cursor:
                half_year_count, half_year_sum = await cursor.fetchone()
            
            # За год (только оплаченные)
            async with db.execute(
                """SELECT COUNT(*), COALESCE(SUM(price), 0) 
                FROM lessons 
                WHERE student_id = ? 
                AND lesson_date >= ?
                AND payment_status = 'paid'
                AND status = 'completed'
                AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)""",
                (student_id, year_ago.strftime('%Y-%m-%d'))
            ) as cursor:
                year_count, year_sum = await cursor.fetchone()
            
            return {
                'month': {'count': month_count or 0, 'sum': month_sum or 0},
                'half_year': {'count': half_year_count or 0, 'sum': half_year_sum or 0},
                'year': {'count': year_count or 0, 'sum': year_sum or 0}
            }
        # === МЕТОДЫ ДЛЯ РАБОТЫ С РАСПИСАНИЕМ ===
    
    async def create_schedule(self, student_id: int, weekday: int, time: str, lesson_format: str, 
                            price: float, duration: int = 60, subject: str = None) -> int:
        """Создать новое расписание с продолжительностью"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO schedules (student_id, weekday, time, lesson_format, price, duration, subject, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, datetime('now'))
            """, (student_id, weekday, time, lesson_format, price, duration, subject))
            
            await db.commit()
            return cursor.lastrowid
    # Добавляем метод обновления продолжительности расписания
    async def update_schedule_duration(self, schedule_id: int, duration: int) -> bool:
        """Обновить продолжительность расписания"""
        if duration <= 0:
            return False
            
        async with aiosqlite.connect(self.db_path) as db:
            # Обновляем расписание
            cursor = await db.execute(
                "UPDATE schedules SET duration = ? WHERE id = ?",
                (duration, schedule_id)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_schedule(self, schedule_id: int) -> Optional[Dict]:
        """Получить расписание по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM schedules WHERE id = ?", (schedule_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def recreate_future_lessons_from_schedule(self, schedule_id: int) -> int:
        """
        Пересоздать все будущие занятия из расписания:
        - Удаляет все будущие занятия (lesson_date >= сегодня, status = 'scheduled')
        - Создает новые занятия на 4 недели вперед с актуальными параметрами расписания
        Возвращает количество созданных занятий
        """
        schedule = await self.get_schedule(schedule_id)
        if not schedule:
            return 0
        
        today = get_local_time().date()
        today_str = today.strftime('%Y-%m-%d')
        
        async with aiosqlite.connect(self.db_path) as db:
            # Удаляем все будущие занятия из этого расписания
            await db.execute("""
                DELETE FROM lessons 
                WHERE schedule_id = ? 
                AND lesson_date >= ?
                AND status = 'scheduled'
            """, (schedule_id, today_str))
            
            # Генерируем даты на 4 недели вперед
            dates = []
            weekday = schedule['weekday']
            days_ahead = weekday - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            
            next_date = today + timedelta(days=days_ahead)
            
            for i in range(4):  # 4 недели
                dates.append(next_date.strftime('%Y-%m-%d'))
                next_date += timedelta(weeks=1)
            
            # Создаем новые занятия прямо в этой же транзакции
            created_count = 0
            for lesson_date in dates:
                # Проверяем существование занятия в этой же транзакции
                async with db.execute("""
                    SELECT COUNT(*) FROM lessons 
                    WHERE student_id = ? AND lesson_date = ? AND lesson_time = ? 
                    AND status != 'cancelled'
                """, (schedule['student_id'], lesson_date, schedule['time'])) as cursor:
                    exists = (await cursor.fetchone())[0] > 0
                
                if not exists:
                    # Создаем занятие прямо в этой транзакции
                    cursor = await db.execute("""
                        INSERT INTO lessons (student_id, lesson_date, lesson_time, subject, lesson_format, 
                                        price, schedule_id, duration, status, created_date)
                        SELECT student_id, ?, time, subject, lesson_format, price, id, duration, 
                            'scheduled', date('now')
                        FROM schedules WHERE id = ?
                    """, (lesson_date, schedule_id))
                    if cursor.lastrowid:
                        created_count += 1
            
            await db.commit()
            return created_count

    async def get_student_schedules(self, student_id: int) -> List[Dict]:
        """Получить все активные расписания ученика"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM schedules 
                WHERE student_id = ? AND is_active = 1 
                ORDER BY weekday, time
            """, (student_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_active_schedules(self) -> List[Dict]:
        """Получить все активные расписания"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT s.*, st.name as student_name 
                FROM schedules s
                JOIN students st ON s.student_id = st.user_id
                WHERE s.is_active = 1
                ORDER BY s.weekday, s.time
            """) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def deactivate_schedule(self, schedule_id: int) -> bool:
        """Деактивировать расписание"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE schedules SET is_active = 0 WHERE id = ?",
                (schedule_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_schedule(self, schedule_id: int, **kwargs) -> bool:
        """Обновить параметры расписания"""
        if not kwargs:
            return False
            
        fields = []
        values = []
        for field, value in kwargs.items():
            if field in ['weekday', 'time', 'lesson_format', 'price', 'subject']:
                fields.append(f"{field} = ?")
                values.append(value)
        
        if not fields:
            return False
            
        values.append(schedule_id)
        query = f"UPDATE schedules SET {', '.join(fields)} WHERE id = ?"
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, values)
            await db.commit()
            return cursor.rowcount > 0

    async def update_schedule_weekday(self, schedule_id: int, weekday: int) -> bool:
        """Обновить день недели расписания
        
        ВНИМАНИЕ: Изменение дня недели НЕ обновляет существующие занятия,
        т.к. они уже привязаны к конкретным датам. Новые занятия будут
        создаваться в новый день недели.
        """
        if not (0 <= weekday <= 6):
            return False
            
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE schedules SET weekday = ? WHERE id = ?",
                (weekday, schedule_id)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_schedule_time(self, schedule_id: int, time: str) -> bool:
        """Обновить время расписания"""
        # Валидация формата времени
        try:
            datetime.strptime(time, '%H:%M')
        except ValueError:
            return False
            
        async with aiosqlite.connect(self.db_path) as db:
            # Обновляем расписание
            cursor = await db.execute(
                "UPDATE schedules SET time = ? WHERE id = ?",
                (time, schedule_id)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_schedule_format(self, schedule_id: int, lesson_format: str) -> bool:
        """Обновить формат занятия в расписании"""
        if lesson_format not in ['online', 'offline']:
            return False
            
        async with aiosqlite.connect(self.db_path) as db:
            # Обновляем расписание
            cursor = await db.execute(
                "UPDATE schedules SET lesson_format = ? WHERE id = ?",
                (lesson_format, schedule_id)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_schedule_price(self, schedule_id: int, price: float) -> bool:
        """Обновить стоимость занятия в расписании"""
        if price <= 0:
            return False
            
        async with aiosqlite.connect(self.db_path) as db:
            # Обновляем расписание
            cursor = await db.execute(
                "UPDATE schedules SET price = ? WHERE id = ?",
                (price, schedule_id)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_student_subject(self, user_id: int, new_subject: str, update_date: bool = True, changed_by: str = 'student') -> Tuple[bool, bool]:
        """Обновить направление ученика. 
        Возвращает (успешно ли обновлено, нужно ли отправить уведомление)"""
        today = get_local_time().strftime('%Y-%m-%d')
        can_notify = await self.can_send_change_notification(user_id, 'subject')
        
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем старое значение перед обновлением
            cursor = await db.execute("SELECT subject FROM students WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            old_subject = row[0] if row and row[0] else None
            
            if update_date and can_notify:
                await db.execute(
                    "UPDATE students SET subject = ?, last_subject_change_date = ? WHERE user_id = ?",
                    (new_subject, today, user_id)
                )
                # Сохраняем в историю, если значение изменилось
                if old_subject != new_subject:
                    await db.execute(
                        """INSERT INTO student_changes_history 
                           (student_id, change_type, old_value, new_value, change_date, changed_by)
                           VALUES (?, 'subject', ?, ?, ?, ?)""",
                        (user_id, old_subject or '', new_subject or '', get_local_time().strftime('%Y-%m-%d %H:%M:%S'), changed_by)
                    )
            else:
                await db.execute(
                    "UPDATE students SET subject = ? WHERE user_id = ?",
                    (new_subject, user_id)
                )
                # Сохраняем в историю даже если не нужно уведомление
                if old_subject != new_subject:
                    await db.execute(
                        """INSERT INTO student_changes_history 
                           (student_id, change_type, old_value, new_value, change_date, changed_by)
                           VALUES (?, 'subject', ?, ?, ?, ?)""",
                        (user_id, old_subject or '', new_subject or '', get_local_time().strftime('%Y-%m-%d %H:%M:%S'), changed_by)
                    )
            await db.commit()
        
        return True, can_notify

    async def delete_student(self, user_id: int) -> bool:
        """Удалить ученика и все связанные данные из базы"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                # Проверяем, существует ли ученик
                student = await self.get_student(user_id)
                if not student:
                    return False
                
                # Удаляем все связанные данные (каскадное удаление)
                # 1. Удаляем историю изменений
                await db.execute(
                    "DELETE FROM student_changes_history WHERE student_id = ?",
                    (user_id,)
                )
                
                # 2. Удаляем расписание
                await db.execute(
                    "DELETE FROM schedules WHERE student_id = ?",
                    (user_id,)
                )
                
                # 3. Удаляем уроки
                await db.execute(
                    "DELETE FROM lessons WHERE student_id = ?",
                    (user_id,)
                )
                
                # 4. Удаляем самого ученика
                cursor = await db.execute(
                    "DELETE FROM students WHERE user_id = ?",
                    (user_id,)
                )
                
                await db.commit()
                return cursor.rowcount > 0
                
            except Exception as e:
                logger.error(f"Ошибка при удалении ученика {user_id}: {e}")
                await db.rollback()
                return False

    # === МЕТОДЫ ДЛЯ РАБОТЫ С ЦЕНАМИ ===
    
    async def get_price_settings(self) -> Optional[Dict]:
        """Получить настройки цен"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM price_settings ORDER BY id DESC LIMIT 1")
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def save_price_settings(self, base_price: float, online_surcharge: float, 
                                  grade_9_surcharge: float, grade_10_11_surcharge: float,
                                  profile_surcharge: float) -> bool:
        """Сохранить настройки цен"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                # Проверяем, есть ли уже настройки
                existing = await self.get_price_settings()
                
                if existing:
                    # Обновляем существующие
                    await db.execute("""
                        UPDATE price_settings 
                        SET base_price = ?, online_surcharge = ?, grade_9_surcharge = ?,
                            grade_10_11_surcharge = ?, profile_surcharge = ?, updated_at = datetime('now')
                        WHERE id = ?
                    """, (base_price, online_surcharge, grade_9_surcharge, 
                          grade_10_11_surcharge, profile_surcharge, existing['id']))
                else:
                    # Создаем новые
                    await db.execute("""
                        INSERT INTO price_settings 
                        (base_price, online_surcharge, grade_9_surcharge, grade_10_11_surcharge, profile_surcharge)
                        VALUES (?, ?, ?, ?, ?)
                    """, (base_price, online_surcharge, grade_9_surcharge,
                          grade_10_11_surcharge, profile_surcharge))
                
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при сохранении настроек цен: {e}")
                await db.rollback()
                return False
    
    async def update_price_setting(self, setting_name: str, value: float) -> bool:
        """Обновить один параметр цены"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                settings = await self.get_price_settings()
                if not settings:
                    return False
                
                column_map = {
                    'base_price': 'base_price',
                    'online_surcharge': 'online_surcharge',
                    'grade_9_surcharge': 'grade_9_surcharge',
                    'grade_10_11_surcharge': 'grade_10_11_surcharge',
                    'profile_surcharge': 'profile_surcharge'
                }
                
                if setting_name not in column_map:
                    return False
                
                await db.execute(
                    f"UPDATE price_settings SET {column_map[setting_name]} = ?, updated_at = datetime('now') WHERE id = ?",
                    (value, settings['id'])
                )
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при обновлении параметра цены: {e}")
                await db.rollback()
                return False
    
    async def calculate_price(self, grade: int, subject: str, lesson_format: str, 
                              custom_price: float = None) -> float:
        """
        Рассчитать цену за час на основе параметров
        Приоритет: индивидуальная цена > настройки цен
        """
        # Если есть индивидуальная цена, используем её
        if custom_price and custom_price > 0:
            return custom_price
        
        # Получаем настройки цен
        settings = await self.get_price_settings()
        if not settings:
            return 0.0  # Нет настроек
        
        # Начинаем с базовой цены
        price = float(settings['base_price'])
        
        # Добавляем надбавку за формат
        if lesson_format == 'online':
            price += float(settings['online_surcharge'])
        
        # Добавляем надбавку за класс
        if grade == 9:
            price += float(settings['grade_9_surcharge'])
        elif grade in [10, 11]:
            price += float(settings['grade_10_11_surcharge'])
        
        # Добавляем надбавку за направление
        if subject and 'профиль' in subject.lower():
            price += float(settings['profile_surcharge'])
        
        return price
    
    async def set_student_custom_price(self, student_id: int, price: float = None) -> bool:
        """Установить индивидуальную цену для ученика (None для удаления)"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                if price is None:
                    await db.execute(
                        "UPDATE students SET custom_price_per_hour = NULL WHERE user_id = ?",
                        (student_id,)
                    )
                else:
                    await db.execute(
                        "UPDATE students SET custom_price_per_hour = ? WHERE user_id = ?",
                        (price, student_id)
                    )
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при установке индивидуальной цены: {e}")
                await db.rollback()
                return False
    
    def get_all_price_combinations(self, settings: Dict) -> List[Dict]:
        """Получить все возможные комбинации цен"""
        combinations = []
        
        base_price = float(settings['base_price'])
        online_surcharge = float(settings['online_surcharge'])
        grade_9_surcharge = float(settings['grade_9_surcharge'])
        grade_10_11_surcharge = float(settings['grade_10_11_surcharge'])
        profile_surcharge = float(settings['profile_surcharge'])
        
        # Все возможные комбинации
        grades = [
            (5, 8, "5-8 класс", 0),
            (9, 9, "9 класс", grade_9_surcharge),
            (10, 11, "10-11 класс", grade_10_11_surcharge)
        ]
        
        subjects = [
            ("база", "база", 0),
            ("профиль", "профиль", profile_surcharge)
        ]
        
        formats = [
            ("offline", "очно", 0),
            ("online", "онлайн", online_surcharge)
        ]
        
        for grade_info in grades:
            for subject_info in subjects:
                for format_info in formats:
                    price = base_price + grade_info[3] + subject_info[2] + format_info[2]
                    combinations.append({
                        'grade_range': grade_info[2],
                        'grade_min': grade_info[0],
                        'grade_max': grade_info[1],
                        'subject': subject_info[1],
                        'format': format_info[1],
                        'price': price
                    })
        
        return combinations

    async def get_student_changes_last_week(self) -> List[Dict]:
        """Получить всех учеников, которые меняли профиль за последнюю неделю"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            week_ago = (get_local_time() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            
            cursor = await db.execute("""
                SELECT DISTINCT s.user_id, s.name, COUNT(h.id) as changes_count
                FROM students s
                JOIN student_changes_history h ON s.user_id = h.student_id
                WHERE h.change_date >= ?
                GROUP BY s.user_id, s.name
                ORDER BY changes_count DESC, s.name
            """, (week_ago,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_student_changes(self, student_id: int, days: int = 7) -> List[Dict]:
        """Получить все изменения конкретного ученика за последние N дней"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            days_ago = (get_local_time() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            
            cursor = await db.execute("""
                SELECT change_type, old_value, new_value, change_date, changed_by
                FROM student_changes_history
                WHERE student_id = ? AND change_date >= ?
                ORDER BY change_date DESC
            """, (student_id, days_ago))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def create_lesson_from_schedule(self, schedule_id: int, lesson_date: str) -> int:
        """Создать занятие из расписания с копированием продолжительности"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO lessons (student_id, lesson_date, lesson_time, subject, lesson_format, 
                                price, schedule_id, duration, status, created_date)
                SELECT student_id, ?, time, subject, lesson_format, price, id, duration, 
                    'scheduled', date('now')
                FROM schedules WHERE id = ?
            """, (lesson_date, schedule_id))
            
            await db.commit()
            return cursor.lastrowid

    async def lesson_exists(self, student_id: int, lesson_date: str, 
                           lesson_time: str = None) -> bool:
        """Проверить, существует ли занятие в указанную дату (не учитывает мягко удаленные)"""
        async with aiosqlite.connect(self.db_path) as db:
            if lesson_time:
                async with db.execute("""
                    SELECT COUNT(*) FROM lessons 
                    WHERE student_id = ? AND lesson_date = ? AND lesson_time = ? 
                    AND status != 'cancelled' AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)
                """, (student_id, lesson_date, lesson_time)) as cursor:
                    result = await cursor.fetchone()
            else:
                async with db.execute("""
                    SELECT COUNT(*) FROM lessons 
                    WHERE student_id = ? AND lesson_date = ? 
                    AND status != 'cancelled' AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)
                """, (student_id, lesson_date)) as cursor:
                    result = await cursor.fetchone()
            
            return result[0] > 0

    async def lesson_was_manually_deleted_from_schedule(self, schedule_id: int, lesson_date: str) -> bool:
        """Проверить, было ли занятие из расписания удалено вручную.

        Проверяет по schedule_id ИЛИ по student_id + время,
        чтобы защититься от случаев пересоздания расписания.
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Сначала получаем данные расписания
            async with db.execute(
                "SELECT student_id, time FROM schedules WHERE id = ?",
                (schedule_id,)
            ) as cursor:
                schedule = await cursor.fetchone()

            if not schedule:
                return False

            student_id, lesson_time = schedule

            # Проверяем по schedule_id ИЛИ по student_id + дата + время
            async with db.execute("""
                SELECT COUNT(*) FROM lessons
                WHERE lesson_date = ?
                AND is_manually_deleted = 1
                AND (
                    schedule_id = ?
                    OR (student_id = ? AND lesson_time = ?)
                )
            """, (lesson_date, schedule_id, student_id, lesson_time)) as cursor:
                result = await cursor.fetchone()
            return result[0] > 0

    async def reschedule_lesson(self, lesson_id: int, new_date: str, 
                               new_time: str = None) -> bool:
        """Перенести занятие на другую дату"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем текущие данные занятия
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM lessons WHERE id = ?", (lesson_id,)
            ) as cursor:
                lesson = await cursor.fetchone()
            
            if not lesson:
                return False
                
            lesson = dict(lesson)
            original_date = lesson['original_date'] or lesson['lesson_date']
            update_time = new_time or lesson['lesson_time']
            
            # Обновляем занятие
            await db.execute("""
                UPDATE lessons 
                SET lesson_date = ?, lesson_time = ?, is_rescheduled = 1, original_date = ?
                WHERE id = ?
            """, (new_date, update_time, original_date, lesson_id))
            await db.commit()
            return True

    async def cancel_lesson(self, lesson_id: int) -> bool:
        """Отменить занятие"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE lessons SET status = 'cancelled' WHERE id = ?",
                (lesson_id,)
            )
            await db.commit()
            return cursor.rowcount > 0
    
    async def cancel_future_lessons_by_schedule(self, schedule_id: int) -> int:
        """Отменить все будущие занятия по расписанию"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                UPDATE lessons 
                SET status = 'cancelled' 
                WHERE schedule_id = ? 
                AND status = 'scheduled'
                AND lesson_date >= date('now')
            """, (schedule_id,))
            await db.commit()
            return cursor.rowcount  # Количество отмененных занятий


    async def complete_lesson(self, lesson_id: int, notes: str = None) -> bool:
        """Отметить занятие как проведенное"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE lessons SET status = 'completed', notes = ? WHERE id = ?",
                (notes, lesson_id)
            )
            await db.commit()
            return cursor.rowcount > 0
    
    async def update_lesson_status(self, lesson_id: int, status: str) -> bool:
        """Обновить статус занятия (scheduled/completed)"""
        if status not in ['scheduled', 'completed', 'cancelled']:
            return False
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE lessons SET status = ? WHERE id = ?",
                (status, lesson_id)
            )
            await db.commit()
            return cursor.rowcount > 0
    
    # Методы для работы с оплатой
    async def update_lesson_payment_status(self, lesson_id: int, payment_status: str) -> bool:
        """Обновить статус оплаты занятия"""
        if payment_status not in ['paid', 'unpaid', 'pending']:
            return False
            
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE lessons SET payment_status = ? WHERE id = ?",
                (payment_status, lesson_id)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_lesson_homework(self, lesson_id: int, homework: str, homework_status: str = 'assigned', 
                                     homework_photo_file_id: str = None, homework_file_id: str = None) -> bool:
        """
        Добавить/обновить домашнее задание
        homework_photo_file_id: file_id фото (None = не изменять, если нужно удалить - передать пустую строку '')
        homework_file_id: file_id файла (None = не изменять, если нужно удалить - передать пустую строку '')
        """
        if homework_status not in ['assigned', 'completed', 'not_done']:
            homework_status = 'assigned'
            
        async with aiosqlite.connect(self.db_path) as db:
            # Формируем список полей для обновления
            fields = ["homework = ?", "homework_status = ?"]
            values = [homework, homework_status]
            
            # Добавляем homework_photo_file_id если передан (включая пустую строку для удаления)
            if homework_photo_file_id is not None:
                if homework_photo_file_id == '':
                    fields.append("homework_photo_file_id = NULL")
                else:
                    fields.append("homework_photo_file_id = ?")
                    values.append(homework_photo_file_id)
            
            # Добавляем homework_file_id если передан (включая пустую строку для удаления)
            if homework_file_id is not None:
                if homework_file_id == '':
                    fields.append("homework_file_id = NULL")
                else:
                    fields.append("homework_file_id = ?")
                    values.append(homework_file_id)
            
            values.append(lesson_id)
            
            query = f"UPDATE lessons SET {', '.join(fields)} WHERE id = ?"
            cursor = await db.execute(query, values)
            await db.commit()
            return cursor.rowcount > 0

    async def get_student_debt(self, student_id: int) -> dict:
        """Получить задолженность ученика"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT 
                    COUNT(*) as unpaid_count,
                    COALESCE(SUM(price), 0) as total_debt
                FROM lessons 
                WHERE student_id = ? 
                AND payment_status = 'unpaid' 
                AND status = 'completed'
            """, (student_id,))
            
            result = await cursor.fetchone()
            return {
                'unpaid_count': result['unpaid_count'],
                'total_debt': float(result['total_debt'])
            }

    async def get_student_homework_smart(self, student_id: int) -> Dict[str, List[Dict]]:
        """
        Получить домашние задания ученика с умным фильтром:
        - Прошлая неделя (занятия за последние 7 дней)
        - Следующая неделя (занятия на следующие 7 дней)
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            today = get_local_time().date()
            week_ago = today - timedelta(days=7)  # Прошлая неделя (7 дней назад)
            week_later = today + timedelta(days=7)  # Следующая неделя (через 7 дней)
            
            # Получаем все занятия ученика (включая без ДЗ, исключая мягко удаленные)
            cursor = await db.execute("""
                SELECT * FROM lessons
                WHERE student_id = ?
                AND status != 'cancelled'
                AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)
                ORDER BY lesson_date ASC, lesson_time ASC
            """, (student_id,))
            
            all_lessons = [dict(row) for row in await cursor.fetchall()]
            
            # Разделяем на категории
            past_week = []  # Прошлая неделя (от 7 дней назад до сегодня)
            next_week = []  # Следующая неделя (от сегодня до через 7 дней)
            
            for lesson in all_lessons:
                lesson_date = datetime.strptime(lesson['lesson_date'], '%Y-%m-%d').date()
                
                # Прошлая неделя: занятия за последние 7 дней (не включая сегодня)
                if week_ago <= lesson_date < today:
                    past_week.append(lesson)
                
                # Следующая неделя: занятия на следующие 7 дней (включая сегодня)
                elif today <= lesson_date <= week_later:
                    next_week.append(lesson)
            
            return {
                'active': past_week,  # Прошлая неделя
                'recent': next_week   # Следующая неделя
            }

    async def get_lessons_ending_soon(self, minutes_before: int = 5, debug: bool = False) -> list:
        """Получить занятия, которые заканчиваются через N минут"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Получаем текущую дату и время (московское время)
            now = get_local_time()
            today_str = now.strftime('%Y-%m-%d')
            
            if debug:
                logger.debug(f"Текущее время: {now.strftime('%Y-%m-%d %H:%M:%S')}")
                logger.debug(f"Ищем занятия на дату: {today_str}")
                logger.debug(f"Ищем занятия, заканчивающиеся через {minutes_before} минут")
            
            # Получаем все запланированные занятия на сегодня
            # Исключаем занятия, для которых уже отправлено уведомление об окончании
            # Фильтруем в Python для точности, т.к. SQLite может иметь проблемы с вычислениями времени
            cursor = await db.execute("""
                SELECT l.*, s.name as student_name, s.user_id as student_id
                FROM lessons l
                JOIN students s ON l.student_id = s.user_id
                WHERE l.lesson_date = ?
                AND l.status = 'scheduled'
                AND l.ending_notification_sent_at IS NULL
                AND (l.is_manually_deleted = 0 OR l.is_manually_deleted IS NULL)
            """, (today_str,))
            
            all_lessons = [dict(row) for row in await cursor.fetchall()]
            
            if debug:
                logger.debug(f"Найдено занятий на сегодня: {len(all_lessons)}")
            
            # Фильтруем занятия в Python
            filtered_results = []
            for lesson in all_lessons:
                try:
                    # Вычисляем время начала и окончания занятия (в московском часовом поясе)
                    lesson_start_naive = datetime.strptime(
                        f"{lesson['lesson_date']} {lesson['lesson_time']}", 
                        '%Y-%m-%d %H:%M'
                    )
                    # Добавляем часовой пояс (московское время)
                    lesson_start = lesson_start_naive.replace(tzinfo=MOSCOW_TZ)
                    duration = lesson.get('duration', 60)  # По умолчанию 60 минут
                    lesson_end = lesson_start + timedelta(minutes=duration)
                    
                    if debug:
                        logger.debug(f"Занятие #{lesson.get('id')}: начало={lesson_start.strftime('%Y-%m-%d %H:%M')}, длительность={duration}мин, окончание={lesson_end.strftime('%Y-%m-%d %H:%M')}")
                    
                    # Проверяем, что занятие уже началось (но еще не закончилось)
                    is_started = lesson_start <= now
                    is_not_ended = now < lesson_end
                    
                    if debug:
                        logger.debug(f"Занятие #{lesson.get('id')}: началось={is_started}, не закончилось={is_not_ended}")
                    
                    if is_started and is_not_ended:
                        # Вычисляем, через сколько минут закончится занятие
                        time_until_end = (lesson_end - now).total_seconds() / 60
                        
                        if debug:
                            logger.debug(f"Занятие #{lesson.get('id')}: до окончания {time_until_end:.1f} мин")
                        
                        # Проверяем, что до окончания осталось от 0 до 5 минут
                        # Диапазон 0-5 минут: уведомление приходит когда до окончания осталось от 0 до 5 минут
                        if 0 <= time_until_end <= 5:
                            if debug:
                                logger.debug(f"Занятие #{lesson.get('id')}: подходит, добавляем")
                            filtered_results.append(lesson)
                        else:
                            if debug:
                                logger.debug(f"Занятие #{lesson.get('id')}: вне диапазона")
                    else:
                        if debug:
                            if not is_started:
                                logger.debug(f"Занятие #{lesson.get('id')}: еще не началось")
                            if not is_not_ended:
                                logger.debug(f"Занятие #{lesson.get('id')}: уже закончилось")
                            
                except Exception as e:
                    logger.warning(f"Ошибка при обработке занятия {lesson.get('id')}: {e}")
                    if debug:
                        logger.exception("Traceback:")
                    continue
            
            if debug:
                logger.debug(f"Итого найдено подходящих занятий: {len(filtered_results)}")
            
            return filtered_results

    async def get_next_scheduled_lesson(self, student_id: int, lesson_date: str, lesson_time: str) -> Optional[Dict]:
        """Получить ближайшее следующее запланированное занятие ученика после указанного"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                """
                SELECT *
                FROM lessons
                WHERE student_id = ?
                  AND status = 'scheduled'
                  AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)
                  AND (
                        lesson_date > ?
                        OR (lesson_date = ? AND lesson_time > ?)
                  )
                ORDER BY lesson_date ASC, lesson_time ASC
                LIMIT 1
                """,
                (student_id, lesson_date, lesson_date, lesson_time)
            )

            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_lessons_starting_soon(self, hours_before: int = 3) -> list:
        """Получить занятия, которые начинаются примерно через N часов (±30 минут)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            now = get_local_time()
            # Вычисляем диапазон: от (hours_before - 0.5) до (hours_before + 0.5) часов
            time_min = now + timedelta(hours=hours_before - 0.5)  # 2.5 часа
            time_max = now + timedelta(hours=hours_before + 0.5)  # 3.5 часа
            
            # Получаем все запланированные занятия на сегодня и завтра
            today_str = now.strftime('%Y-%m-%d')
            tomorrow = now + timedelta(days=1)
            tomorrow_str = tomorrow.strftime('%Y-%m-%d')
            
            # Получаем все занятия на сегодня и завтра
            cursor = await db.execute("""
                SELECT l.*, s.name as student_name, s.user_id
                FROM lessons l
                JOIN students s ON l.student_id = s.user_id
                WHERE l.lesson_date IN (?, ?)
                AND l.status = 'scheduled'
                AND (l.is_manually_deleted = 0 OR l.is_manually_deleted IS NULL)
                ORDER BY l.lesson_date, l.lesson_time
            """, (today_str, tomorrow_str))
            
            all_lessons = [dict(row) for row in await cursor.fetchall()]
            
            # Фильтруем по точному времени до начала занятия
            results = []
            for lesson in all_lessons:
                lesson_datetime_naive = datetime.strptime(
                    f"{lesson['lesson_date']} {lesson['lesson_time']}", 
                    '%Y-%m-%d %H:%M'
                )
                # Добавляем часовой пояс (московское время)
                lesson_datetime = lesson_datetime_naive.replace(tzinfo=MOSCOW_TZ)
                hours_until = (lesson_datetime - now).total_seconds() / 3600
                
                # Проверяем, что занятие начинается в диапазоне 2.5-3.5 часов
                if 2.5 <= hours_until <= 3.5:
                    results.append(lesson)
            
            return results

    async def get_lessons_without_start_notification(self, lesson_date: str) -> list:
        """Получить занятия на дату, которым ещё не отправили уведомление о начале"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT l.*, s.name as student_name, s.username, s.user_id
                FROM lessons l
                LEFT JOIN students s ON l.student_id = s.user_id
                WHERE l.lesson_date = ?
                AND l.status = 'scheduled'
                AND (l.start_notification_sent_at IS NULL OR l.start_notification_sent_at = '')
                AND (l.is_manually_deleted = 0 OR l.is_manually_deleted IS NULL)
                ORDER BY l.lesson_time
            """, (lesson_date,))
            return [dict(row) for row in await cursor.fetchall()]

    async def get_lessons_24h_before(self) -> list:
        """Получить занятия, которые начинаются примерно через 24 часа (23-25 часов)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Время через 24 часа (проверяем диапазон 23-25 часов для точности)
            target_time = get_local_time() + timedelta(hours=24)
            target_date = target_time.strftime('%Y-%m-%d')
            start_time = (target_time - timedelta(minutes=15)).strftime('%H:%M')  # ±15 мин точность
            end_time = (target_time + timedelta(minutes=15)).strftime('%H:%M')
            
            cursor = await db.execute("""
                SELECT l.*, s.name as student_name, s.user_id
                FROM lessons l
                JOIN students s ON l.student_id = s.user_id
                WHERE l.lesson_date = ?
                AND l.lesson_time BETWEEN ? AND ?
                AND l.status = 'scheduled'
                AND (l.is_manually_deleted = 0 OR l.is_manually_deleted IS NULL)
            """, (target_date, start_time, end_time))
            
            return [dict(row) for row in await cursor.fetchall()]

    async def get_unconfirmed_lessons(self) -> list:
        """Получить занятия, по которым отправлено уведомление с кнопкой подтверждения,
        но ученик еще не подтвердил участие (прошло более часа после отправки).
        Только занятия, которые ещё не начались и по которым ещё не слали повторное напоминание."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute("""
                SELECT l.*, s.name as student_name, s.user_id
                FROM lessons l
                JOIN students s ON l.student_id = s.user_id
                WHERE l.confirmation_sent_at IS NOT NULL
                AND (l.confirmation_status IS NULL)
                AND l.status = 'scheduled'
                AND (l.is_manually_deleted = 0 OR l.is_manually_deleted IS NULL)
                AND datetime(l.confirmation_sent_at, '+1 hour') < datetime('now')
                AND datetime(l.lesson_date || ' ' || l.lesson_time) > datetime('now')
            """)

            return [dict(row) for row in await cursor.fetchall()]

    async def update_lesson_confirmation(self, lesson_id: int, confirmation_status: str, confirmation_sent_at: str = None):
        """Обновить статус подтверждения урока"""
        async with aiosqlite.connect(self.db_path) as db:
            if confirmation_sent_at:
                await db.execute("""
                    UPDATE lessons 
                    SET confirmation_status = ?, confirmation_sent_at = ?
                    WHERE id = ?
                """, (confirmation_status, confirmation_sent_at, lesson_id))
            else:
                await db.execute("""
                    UPDATE lessons 
                    SET confirmation_status = ?
                    WHERE id = ?
                """, (confirmation_status, lesson_id))
            await db.commit()
    
    async def update_lesson_ending_notification(self, lesson_id: int, notification_time: str):
        """Отметить, что уведомление об окончании занятия отправлено"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE lessons 
                SET ending_notification_sent_at = ?
                WHERE id = ?
            """, (notification_time, lesson_id))
            await db.commit()

    async def update_lesson_start_notification(self, lesson_id: int, notification_time: str):
        """Отметить, что уведомление о начале занятия отправлено"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE lessons 
                SET start_notification_sent_at = ?
                WHERE id = ?
            """, (notification_time, lesson_id))
            await db.commit()

    async def get_all_debtors(self) -> list:
        """Получить список всех учеников с задолженностью"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            cursor = await db.execute("""
                SELECT 
                    s.user_id,
                    s.name,
                    s.username,
                    s.phone,
                    COUNT(l.id) as unpaid_count,
                    COALESCE(SUM(l.price), 0) as total_debt
                FROM students s
                JOIN lessons l ON s.user_id = l.student_id
                WHERE l.payment_status = 'unpaid'
                AND l.status = 'completed'
                AND (l.is_manually_deleted = 0 OR l.is_manually_deleted IS NULL)
                GROUP BY s.user_id, s.name, s.username, s.phone
                HAVING total_debt > 0
                ORDER BY total_debt DESC
            """)
            
            return [dict(row) for row in await cursor.fetchall()]
    
    async def get_student_unpaid_lessons(self, student_id: int) -> list:
        """Получить все неоплаченные занятия ученика"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            cursor = await db.execute("""
                SELECT *
                FROM lessons
                WHERE student_id = ?
                AND payment_status = 'unpaid'
                AND status = 'completed'
                AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)
                ORDER BY lesson_date DESC
            """, (student_id,))
            
            return [dict(row) for row in await cursor.fetchall()]
    
    async def delete_lesson(self, lesson_id: int) -> bool:
        """Мягкое удаление занятия (помечает как удаленное вручную)"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE lessons SET is_manually_deleted = 1 WHERE id = ?",
                (lesson_id,)
            )
            await db.commit()
            return cursor.rowcount > 0
    
    async def cleanup_old_deleted_lessons(self, days: int = 14) -> int:
        """
        Физически удалить старые мягко удаленные занятия (старше указанного количества дней)
        Возвращает количество удаленных занятий
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Вычисляем дату, старше которой нужно удалить занятия
            cutoff_date = (get_local_time() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # Удаляем занятия, которые:
            # 1. Помечены как удаленные вручную (is_manually_deleted = 1)
            # 2. Дата занятия старше cutoff_date
            cursor = await db.execute("""
                DELETE FROM lessons 
                WHERE is_manually_deleted = 1 
                AND lesson_date < ?
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
            await db.commit()
            return deleted_count
    
    async def get_lesson_by_id(self, lesson_id: int) -> Optional[Dict]:
        """Получить занятие по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM lessons WHERE id = ?",
                (lesson_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def get_lessons_smart_filter(self, student_id: int) -> Dict[str, List[Dict]]:
        """
        Получить занятия ученика с умной фильтрацией:
        - Неоплаченные (все, независимо от даты)
        - Предстоящие (на неделю вперед)
        - Прошедшие (за неделю назад)
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            today = get_local_time().date()
            week_ago = today - timedelta(days=7)
            week_later = today + timedelta(days=7)
            
            # Получаем все занятия ученика (кроме отмененных и мягко удаленных)
            cursor = await db.execute("""
                SELECT * FROM lessons
                WHERE student_id = ?
                AND status != 'cancelled'
                AND (is_manually_deleted = 0 OR is_manually_deleted IS NULL)
                ORDER BY lesson_date DESC, lesson_time DESC
            """, (student_id,))
            
            all_lessons = [dict(row) for row in await cursor.fetchall()]
            
            # Разделяем на категории
            unpaid_lessons = []  # Все неоплаченные завершенные
            upcoming_lessons = []  # Предстоящие на неделю
            past_lessons = []  # Прошедшие за неделю
            
            for lesson in all_lessons:
                lesson_date = datetime.strptime(lesson['lesson_date'], '%Y-%m-%d').date()
                
                # Неоплаченные завершенные занятия (независимо от даты)
                if lesson['payment_status'] == 'unpaid' and lesson['status'] == 'completed':
                    unpaid_lessons.append(lesson)
                # Предстоящие занятия (на неделю вперед)
                elif lesson['status'] == 'scheduled' and today <= lesson_date <= week_later:
                    upcoming_lessons.append(lesson)
                # Прошедшие занятия (за неделю, оплаченные)
                elif lesson_date >= week_ago and lesson_date < today and lesson['payment_status'] == 'paid':
                    past_lessons.append(lesson)
            
            return {
                'unpaid': unpaid_lessons,
                'upcoming': upcoming_lessons,
                'past': past_lessons
            }

    async def get_today_lessons(self) -> List[Dict]:
        """Получить все занятия на сегодня"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            today = get_local_time().date()
            today_str = today.strftime('%Y-%m-%d')
            
            cursor = await db.execute("""
                SELECT l.*, s.name as student_name, s.grade, s.subject
                FROM lessons l
                JOIN students s ON l.student_id = s.user_id
                WHERE l.lesson_date = ?
                AND l.status != 'cancelled'
                AND (l.is_manually_deleted = 0 OR l.is_manually_deleted IS NULL)
                ORDER BY l.lesson_time ASC
            """, (today_str,))
            
            return [dict(row) for row in await cursor.fetchall()]

    async def get_week_lessons_summary(self) -> Dict[str, Dict]:
        """
        Получить краткую сводку занятий на неделю (сегодня + 6 дней вперед)
        Возвращает словарь: {день_недели: {количество, первое_время, последнее_время, список_занятий}}
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            today = get_local_time().date()
            week_end = today + timedelta(days=6)
            today_str = today.strftime('%Y-%m-%d')
            week_end_str = week_end.strftime('%Y-%m-%d')
            
            cursor = await db.execute("""
                SELECT l.*, s.name as student_name, s.grade, s.subject
                FROM lessons l
                JOIN students s ON l.student_id = s.user_id
                WHERE l.lesson_date >= ? AND l.lesson_date <= ?
                AND l.status != 'cancelled'
                AND (l.is_manually_deleted = 0 OR l.is_manually_deleted IS NULL)
                ORDER BY l.lesson_date ASC, l.lesson_time ASC
            """, (today_str, week_end_str))
            
            lessons = [dict(row) for row in await cursor.fetchall()]
            
            # Группируем по дням
            week_summary = {}
            weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
            
            for lesson in lessons:
                lesson_date = datetime.strptime(lesson['lesson_date'], '%Y-%m-%d').date()
                weekday_num = lesson_date.weekday()
                weekday_name = weekday_names[weekday_num]
                
                if weekday_name not in week_summary:
                    week_summary[weekday_name] = {
                        'date': lesson_date,
                        'date_str': lesson['lesson_date'],
                        'count': 0,
                        'first_time': None,
                        'last_time': None,
                        'lessons': []
                    }
                
                week_summary[weekday_name]['count'] += 1
                week_summary[weekday_name]['lessons'].append(lesson)
                
                lesson_time = lesson['lesson_time']
                if not week_summary[weekday_name]['first_time'] or lesson_time < week_summary[weekday_name]['first_time']:
                    week_summary[weekday_name]['first_time'] = lesson_time
                if not week_summary[weekday_name]['last_time'] or lesson_time > week_summary[weekday_name]['last_time']:
                    week_summary[weekday_name]['last_time'] = lesson_time
            
            return week_summary

    async def get_week_lessons_detailed(self) -> List[Dict]:
        """Получить подробный список всех занятий на неделю (сегодня + 6 дней вперед)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            today = get_local_time().date()
            week_end = today + timedelta(days=6)
            today_str = today.strftime('%Y-%m-%d')
            week_end_str = week_end.strftime('%Y-%m-%d')
            
            cursor = await db.execute("""
                SELECT l.*, s.name as student_name, s.grade, s.subject
                FROM lessons l
                JOIN students s ON l.student_id = s.user_id
                WHERE l.lesson_date >= ? AND l.lesson_date <= ?
                AND l.status != 'cancelled'
                AND (l.is_manually_deleted = 0 OR l.is_manually_deleted IS NULL)
                ORDER BY l.lesson_date ASC, l.lesson_time ASC
            """, (today_str, week_end_str))
            
            return [dict(row) for row in await cursor.fetchall()]

    # === МЕТОДЫ ДЛЯ РАБОТЫ С ЗАПЛАНИРОВАННЫМИ ЗАДАЧАМИ ===
    
    async def create_scheduled_task(self, lesson_id: Optional[int], task_type: str, 
                                   scheduled_time: str, execution_data: Optional[Dict] = None,
                                   max_retries: int = 3) -> int:
        """Создать запланированную задачу"""
        import json
        async with aiosqlite.connect(self.db_path) as db:
            execution_data_json = json.dumps(execution_data) if execution_data else None
            cursor = await db.execute("""
                INSERT INTO scheduled_tasks 
                (lesson_id, task_type, scheduled_time, status, execution_data, max_retries)
                VALUES (?, ?, ?, 'pending', ?, ?)
            """, (lesson_id, task_type, scheduled_time, execution_data_json, max_retries))
            await db.commit()
            return cursor.lastrowid
    
    async def get_pending_tasks(self, limit: int = 20) -> List[Dict]:
        """Получить задачи, готовые к выполнению (статус pending, время наступило)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            now = get_local_time().strftime('%Y-%m-%d %H:%M:%S')
            cursor = await db.execute("""
                SELECT * FROM scheduled_tasks
                WHERE status = 'pending' AND scheduled_time <= ?
                ORDER BY scheduled_time ASC
                LIMIT ?
            """, (now, limit))
            return [dict(row) for row in await cursor.fetchall()]
    
    async def update_task_status(self, task_id: int, status: str, 
                                error_message: Optional[str] = None) -> bool:
        """Обновить статус задачи"""
        async with aiosqlite.connect(self.db_path) as db:
            now = get_local_time().strftime('%Y-%m-%d %H:%M:%S')
            if status == 'completed':
                cursor = await db.execute("""
                    UPDATE scheduled_tasks 
                    SET status = ?, executed_at = ?
                    WHERE id = ?
                """, (status, now, task_id))
            elif status == 'failed':
                cursor = await db.execute("""
                    UPDATE scheduled_tasks 
                    SET status = ?, executed_at = ?, error_message = ?
                    WHERE id = ?
                """, (status, now, error_message, task_id))
            else:
                cursor = await db.execute("""
                    UPDATE scheduled_tasks 
                    SET status = ?
                    WHERE id = ?
                """, (status, task_id))
            await db.commit()
            return cursor.rowcount > 0
    
    async def increment_task_retry(self, task_id: int, new_scheduled_time: str) -> bool:
        """Увеличить счетчик попыток и обновить время выполнения"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                UPDATE scheduled_tasks 
                SET retry_count = retry_count + 1, scheduled_time = ?
                WHERE id = ?
            """, (new_scheduled_time, task_id))
            await db.commit()
            return cursor.rowcount > 0
    
    async def cancel_lesson_tasks(self, lesson_id: int, task_types: Optional[List[str]] = None) -> int:
        """Отменить все задачи для занятия (или определенных типов)"""
        async with aiosqlite.connect(self.db_path) as db:
            if task_types:
                placeholders = ','.join(['?'] * len(task_types))
                cursor = await db.execute(f"""
                    UPDATE scheduled_tasks 
                    SET status = 'cancelled'
                    WHERE lesson_id = ? AND task_type IN ({placeholders}) AND status = 'pending'
                """, (lesson_id, *task_types))
            else:
                cursor = await db.execute("""
                    UPDATE scheduled_tasks 
                    SET status = 'cancelled'
                    WHERE lesson_id = ? AND status = 'pending'
                """, (lesson_id,))
            await db.commit()
            return cursor.rowcount
    
    async def task_exists(self, lesson_id: Optional[int], task_type: str, 
                         status: str = 'pending') -> bool:
        """Проверить, существует ли активная задача определенного типа"""
        async with aiosqlite.connect(self.db_path) as db:
            if lesson_id is not None:
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM scheduled_tasks
                    WHERE lesson_id = ? AND task_type = ? AND status = ?
                """, (lesson_id, task_type, status))
            else:
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM scheduled_tasks
                    WHERE lesson_id IS NULL AND task_type = ? AND status = ?
                """, (task_type, status))
            result = await cursor.fetchone()
            return result[0] > 0
    
    async def get_lesson_tasks(self, lesson_id: int, status: Optional[str] = None) -> List[Dict]:
        """Получить все задачи для занятия"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if status:
                cursor = await db.execute("""
                    SELECT * FROM scheduled_tasks
                    WHERE lesson_id = ? AND status = ?
                    ORDER BY scheduled_time ASC
                """, (lesson_id, status))
            else:
                cursor = await db.execute("""
                    SELECT * FROM scheduled_tasks
                    WHERE lesson_id = ?
                    ORDER BY scheduled_time ASC
                """, (lesson_id,))
            return [dict(row) for row in await cursor.fetchall()]
    
    async def cleanup_old_completed_tasks(self, days: int = 30) -> int:
        """Удалить выполненные задачи старше N дней"""
        async with aiosqlite.connect(self.db_path) as db:
            cutoff_date = (get_local_time() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            cursor = await db.execute("""
                DELETE FROM scheduled_tasks
                WHERE status = 'completed' AND executed_at < ?
            """, (cutoff_date,))
            await db.commit()
            return cursor.rowcount

