from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date


# === Модели для ученика ===

class StudentProfile(BaseModel):
    """Профиль ученика"""
    user_id: int
    name: str
    username: Optional[str] = None
    phone: str
    grade: int
    subject: Optional[str] = None  # база/профиль (только для 10-11 классов)
    registration_date: Optional[str] = None

    # Флаги возможности изменения
    can_change_name: bool = True
    can_change_grade: bool = True
    can_change_subject: bool = True

    # Даты последних изменений
    last_name_change: Optional[str] = None
    last_grade_change: Optional[str] = None
    last_subject_change: Optional[str] = None


class Lesson(BaseModel):
    """Занятие"""
    id: int
    lesson_date: str  # YYYY-MM-DD
    lesson_time: str  # HH:MM
    duration: int = 60  # минуты
    price: float
    status: str  # scheduled, completed, cancelled
    payment_status: str = "unpaid"  # paid, unpaid, pending
    lesson_format: Optional[str] = None  # online, offline

    # ДЗ
    homework: Optional[str] = None
    homework_status: Optional[str] = None  # assigned, completed, not_done

    # Вычисляемые поля
    has_homework: bool = False
    time_range: Optional[str] = None  # "15:00 - 16:00"
    formatted_date: Optional[str] = None  # "15.01 (Пн)"


class LessonsHistory(BaseModel):
    """История занятий с умной фильтрацией"""
    unpaid: List[Lesson] = []
    upcoming: List[Lesson] = []
    past: List[Lesson] = []

    # Сумма долга
    total_debt: float = 0


class HomeworkItem(BaseModel):
    """Элемент списка ДЗ"""
    id: int
    lesson_date: str
    lesson_time: str
    duration: int = 60
    has_homework: bool = False
    homework_status: Optional[str] = None
    formatted_date: Optional[str] = None


class HomeworkList(BaseModel):
    """Список ДЗ с умной фильтрацией"""
    active: List[HomeworkItem] = []  # Прошлая неделя
    recent: List[HomeworkItem] = []  # Следующая неделя


class HomeworkDetail(BaseModel):
    """Детали ДЗ"""
    id: int
    lesson_date: str
    lesson_time: str
    duration: int = 60
    homework: Optional[str] = None
    homework_status: Optional[str] = None
    homework_photo_file_id: Optional[str] = None
    homework_file_id: Optional[str] = None
    homework_file_name: Optional[str] = None

    formatted_date: Optional[str] = None
    time_range: Optional[str] = None


class LessonDetail(BaseModel):
    """Детальная информация о занятии"""
    id: int
    lesson_date: str
    lesson_time: str
    duration: int = 60
    price: float
    status: str
    payment_status: str = "unpaid"
    lesson_format: Optional[str] = None

    # ДЗ
    homework: Optional[str] = None
    homework_status: Optional[str] = None
    homework_photo_file_id: Optional[str] = None
    homework_file_id: Optional[str] = None
    homework_file_name: Optional[str] = None

    # Вычисляемые поля
    formatted_date: Optional[str] = None
    time_range: Optional[str] = None


class FileUrlResponse(BaseModel):
    """Ответ с URL файла"""
    url: str
    file_name: Optional[str] = None
    file_size: Optional[int] = None


# === Модели для запросов ===

class UpdateNameRequest(BaseModel):
    """Запрос на изменение имени"""
    name: str = Field(..., min_length=2, max_length=100)


class UpdateGradeRequest(BaseModel):
    """Запрос на изменение класса"""
    grade: int = Field(..., ge=5, le=11)


class UpdateSubjectRequest(BaseModel):
    """Запрос на изменение направления"""
    subject: str = Field(..., pattern="^(база|профиль|base|profile)$")


# === Модели для ответов ===

class UpdateProfileResponse(BaseModel):
    """Ответ на изменение профиля"""
    success: bool
    message: str
    can_change_again: Optional[str] = None  # Дата, когда можно будет изменить снова


class ErrorResponse(BaseModel):
    """Ошибка"""
    detail: str


# === Модели для учителя ===

class RoleResponse(BaseModel):
    """Роль пользователя"""
    role: str  # "teacher" | "student"


class TeacherStudent(BaseModel):
    """Ученик в списке учителя"""
    user_id: int
    name: str
    grade: int
    subject: Optional[str] = None
    phone: str
    registration_date: Optional[str] = None
    total_debt: float = 0
    unpaid_lessons_count: int = 0
    is_new: bool = False


class TeacherLesson(BaseModel):
    """Занятие в расписании учителя"""
    id: int
    student_id: int
    student_name: str
    lesson_date: str
    lesson_time: str
    duration: int = 60
    price: float
    status: str
    payment_status: str
    lesson_format: Optional[str] = None
    has_homework: bool = False
    time_range: Optional[str] = None
    formatted_date: Optional[str] = None


class DashboardStats(BaseModel):
    """Статистика для дашборда учителя"""
    new_students_count: int = 0
    debtors_count: int = 0
    today_lessons_count: int = 0
    today_lessons: List[TeacherLesson] = []


class TeacherStudentDetail(BaseModel):
    """Детальная карточка ученика для учителя"""
    user_id: int
    name: str
    grade: int
    subject: Optional[str] = None
    phone: str
    registration_date: Optional[str] = None
    registration_format: Optional[str] = None
    total_debt: float = 0
    unpaid_lessons_count: int = 0
    total_lessons_count: int = 0
    is_new: bool = False


class WeekSchedule(BaseModel):
    """Расписание на неделю"""
    days: dict[str, List[TeacherLesson]] = {}  # date -> lessons


class PriceSettings(BaseModel):
    """Настройки цен"""
    base_price: float = 0
    online_surcharge: float = 0
    grade_9_surcharge: float = 0
    grade_10_11_surcharge: float = 0
    profile_surcharge: float = 0
    updated_at: Optional[str] = None


class UpdatePriceSettingsRequest(BaseModel):
    """Запрос на обновление настроек цен"""
    base_price: float
    online_surcharge: float
    grade_9_surcharge: float
    grade_10_11_surcharge: float
    profile_surcharge: float


class TeacherLessonDetail(BaseModel):
    """Детали занятия для учителя"""
    id: int
    student_id: int
    student_name: str
    lesson_date: str
    lesson_time: str
    duration: int = 60
    price: float
    status: str
    payment_status: str
    lesson_format: Optional[str] = None
    homework: Optional[str] = None
    homework_status: Optional[str] = None
    time_range: Optional[str] = None
    formatted_date: Optional[str] = None


class TeacherStudentLessons(BaseModel):
    """Таймлайн занятий ученика для учителя"""
    upcoming: List[TeacherLesson] = []
    recent: List[TeacherLesson] = []
    has_more: bool = False


class UpdateLessonPaymentRequest(BaseModel):
    """Запрос на обновление статуса оплаты"""
    payment_status: str = Field(..., pattern="^(paid|unpaid|pending)$")


class UpdateLessonStatusRequest(BaseModel):
    """Запрос на обновление статуса занятия"""
    status: str = Field(..., pattern="^(scheduled|completed|cancelled)$")


class UpdateLessonHomeworkRequest(BaseModel):
    """Запрос на обновление ДЗ"""
    homework: str
