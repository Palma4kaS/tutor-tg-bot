from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton,
                          InlineKeyboardMarkup, InlineKeyboardButton)
from datetime import datetime, date
from calendar import monthcalendar
from typing import List, Dict, Optional

from bot_template.utils.formatting import WEEKDAYS_RU, format_date_with_weekday

# Главная клавиатура бота (отображается внизу экрана)
main = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='📚 Мои занятия'), KeyboardButton(text='📖 ДЗ')],  # Занятия и ДЗ
    [KeyboardButton(text='Доп. материал'), KeyboardButton(text='Мой профиль')]  # Дополнительные кнопки
],
resize_keyboard=True,  # Подгонка размера под экран
input_field_placeholder='Выберите пункт меню ниже')  # Подсказка в поле ввода

#Админ паель учителя
admin_main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='📅 Расписание')],
        [KeyboardButton(text='👥 Мои ученики'), KeyboardButton(text='💰 Должники')],
        [KeyboardButton(text='🆕 Новые ученики')],
        [KeyboardButton(text='📝 Изменения учеников'), KeyboardButton(text='⚙️ Настройки')]
    ],
    resize_keyboard=True,
    input_field_placeholder='Выберите действие'
)

# Клавиатура для приветствия зарегистрированных пользователей (модифицированная main)

first_time_user = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💰 Узнать цену своего первого занятия")]
    ],
    resize_keyboard=True,
    input_field_placeholder="Запишись на первое занятие"
)

# Функция для генерации списка учеников (Inline)
def generate_students_list(students: list, is_new_students: bool = False) -> InlineKeyboardMarkup:
    """Генерирует Inline-клавиатуру со списком учеников"""
    buttons = []
    
    for student in students:
        # Формат: "👤 Имя Фамилия (класс)"
        button_text = f"👤 {student['name']} ({student['grade']} класс)"
        # Если это список новых учеников, используем отдельный callback
        if is_new_students:
            callback_data = f"new_student_{student['user_id']}"
        else:
            callback_data = f"view_student_{student['user_id']}"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])
    
    # Добавляем кнопки навигации
    buttons.append([InlineKeyboardButton(text="🔍 Найти ученика", callback_data="search_student")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_admin")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def back_to_student_profile(student_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 К профилю ученика", callback_data=f"view_student_{student_id}")]
        ]
    )

def generate_student_card_keyboard(student_id: int) -> InlineKeyboardMarkup:
    """Клавиатура карточки ученика"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Расписание", callback_data=f"schedule_{student_id}"),
            InlineKeyboardButton(text="➕ Добавить занятие", callback_data=f"add_manual_lesson_{student_id}")
            #InlineKeyboardButton(text="📖 История", callback_data=f"lessons_history_{student_id}")
        ],
        [
            InlineKeyboardButton(text="📖 История", callback_data=f"lessons_history_{student_id}"),
            InlineKeyboardButton(text="📖 ДЗ", callback_data=f"view_homework_{student_id}"),
            # InlineKeyboardButton(text="💰 Оплата", callback_data=f"manage_payments_{student_id}"),
            # InlineKeyboardButton(text="📊 Статистика", callback_data=f"student_stats_{student_id}")
        ],
        # [
        #     InlineKeyboardButton(text="📖 ДЗ", callback_data=f"view_homework_{student_id}")
        # ],
        [
            InlineKeyboardButton(text="💰 Оплата", callback_data=f"manage_payments_{student_id}"),
            InlineKeyboardButton(text="📊 Статистика", callback_data=f"student_stats_{student_id}")
        ],
        [InlineKeyboardButton(text="✏️ Редактировать профиль", callback_data=f"edit_student_{student_id}")],
        [InlineKeyboardButton(text="◀️ К списку учеников", callback_data="show_students_list")]
    ])

# Клавиатура "Назад к списку учеников"
back_to_students = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔙 К списку учеников", callback_data="show_students_list")]
])



# Inline клавиатура для выбора формата обучения
format = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="💻 Онлайн", callback_data="format_online"),
        InlineKeyboardButton(text="🏫 Оффлайн", callback_data="format_offline")
    ]
])

# Inline клавиатура для выбора класса
number_class = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='5', callback_data='class_5'), 
     InlineKeyboardButton(text='6', callback_data='class_6'), 
     InlineKeyboardButton(text='7', callback_data='class_7')],
    [InlineKeyboardButton(text='8', callback_data='class_8'), 
     InlineKeyboardButton(text='9', callback_data='class_9'), 
     InlineKeyboardButton(text='10', callback_data='class_10')],
    [InlineKeyboardButton(text='11', callback_data='class_11')]
])

# Inline клавиатура для выбора направления (база/профиль)
var = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='📐 База', callback_data='base'), 
     InlineKeyboardButton(text='📈 Профиль', callback_data='profil')]
])

def admin_edit_student_profile_keyboard(student_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для редактирования профиля ученика учителем (направление всегда доступно)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text='✏️ Изменить имя', callback_data=f'admin_change_name_{student_id}'),
            InlineKeyboardButton(text='🎓 Изменить класс', callback_data=f'admin_change_grade_{student_id}')
        ],
        [
            InlineKeyboardButton(text='📊 Изменить направление', callback_data=f'admin_change_subject_{student_id}')
        ],
        [
            InlineKeyboardButton(text="💰 Цена занятия", callback_data=f"student_custom_price_{student_id}")
        ],
        [
            InlineKeyboardButton(text='🗑️ Удалить ученика', callback_data=f'confirm_delete_student_{student_id}')
        ],
        [
            InlineKeyboardButton(text='◀️ К профилю', callback_data=f'view_student_{student_id}')
        ]
    ])

# Inline клавиатура для вопроса "откуда узнали"
feedback_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="👥 От друзей", callback_data="feedback_friends"),
        InlineKeyboardButton(text="📱 ТикТок", callback_data="feedback_social")
    ],
    [
        InlineKeyboardButton(text="🔍 В интернете", callback_data="feedback_search"),
        InlineKeyboardButton(text="💬 Другое", callback_data="feedback_other")
    ]
])

# Inline клавиатура для дополнительных материалов
dop_material = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text='📚 Для ОГЭ', url='https://telegra.ph/Test-1-09-03-4'),
        InlineKeyboardButton(text='📖 Для ЕГЭ', url='https://telegra.ph/Dop-materialy-dlya-podgotovki-dlya-EGEH-09-03')
    ],
    [
        InlineKeyboardButton(text='🏠 Главное меню', callback_data='back_to_main')
    ]
])

# Кнопка возврата в главное меню
back_button = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_main")]
])

def profile_change_keyboard(grade: int) -> InlineKeyboardMarkup:
    """Клавиатура для изменения профиля ученика (показывает направление только для классов >= 10)"""
    buttons = [
        [
            InlineKeyboardButton(text='✏️ Изменить имя', callback_data='change_name'),
            InlineKeyboardButton(text='🎓 Изменить класс', callback_data='change_grade')
        ]
    ]
    
    # Показываем кнопку изменения направления только для классов 10-11
    if grade >= 10:
        buttons.append([
            InlineKeyboardButton(text='📊 Изменить направление', callback_data='change_profil')
        ])
    
    buttons.append([
        InlineKeyboardButton(text='🏠 Главное меню', callback_data='back_to_main')
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

subject_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [
    InlineKeyboardButton(text="📊 Профиль", callback_data="subject_profile"),
    InlineKeyboardButton(text="📐 Базовый", callback_data="subject_base")
    ],
    [InlineKeyboardButton(text="❌ Отмена", callback_data="show_profile")]
])

def schedule_today_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для расписания на сегодня"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 На всю неделю", callback_data="schedule_week_summary")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_admin_main")]
    ])

def schedule_week_summary_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для краткого расписания на неделю"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Обратно к сегодняшнему расписанию", callback_data="schedule_today")],
        [InlineKeyboardButton(text="📋 Подробное расписание на неделю", callback_data="schedule_week_detailed")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_admin_main")]
    ])

def schedule_week_detailed_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для подробного расписания на неделю"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Краткое расписание", callback_data="schedule_week_summary")],
        [InlineKeyboardButton(text="◀️ К сегодняшнему", callback_data="schedule_today")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_admin_main")]
    ])

def schedule_management_keyboard(student_id: int, schedules: list) -> InlineKeyboardMarkup:
    """Клавиатура управления расписанием ученика"""
    keyboard = []
    
    # Кнопка добавления нового расписания
    keyboard.append([InlineKeyboardButton(text="➕ Добавить расписание", callback_data=f"add_schedule_{student_id}")])
    
    # Кнопки для каждого существующего расписания
    weekday_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for schedule in schedules:
        day_name = weekday_names[schedule['weekday']]
        format_emoji = "🏠" if schedule['lesson_format'] == "offline" else "💻"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{format_emoji} {day_name} {schedule['time']} - {int(schedule['price'])}₽",
                callback_data=f"edit_schedule_item_{schedule['id']}"  # НОВЫЙ callback
            )
        ])
    
    # Кнопка назад
    keyboard.append([InlineKeyboardButton(text="◀️ К ученику", callback_data=f"view_student_{student_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def weekday_selection_keyboard(student_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора дня недели"""
    weekdays = [
        ("Понедельник", "weekday_0"),
        ("Вторник", "weekday_1"),
        ("Среда", "weekday_2"),
        ("Четверг", "weekday_3"),
        ("Пятница", "weekday_4"),
        ("Суббота", "weekday_5"),
        ("Воскресенье", "weekday_6")
    ]
    
    keyboard = []
    for day_name, callback_data in weekdays:
        keyboard.append([InlineKeyboardButton(text=day_name, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"schedule_{student_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def schedule_item_actions_keyboard(schedule_id: int, student_id: int) -> InlineKeyboardMarkup:
    """Клавиатура действий с конкретным элементом расписания"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Изменить", callback_data=f"modify_schedule_{schedule_id}"),
            InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_schedule_{schedule_id}")
        ],
        [InlineKeyboardButton(text="◀️ К расписанию", callback_data=f"schedule_{student_id}")]
    ])

def schedule_delete_confirmation_keyboard(schedule_id: int, student_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления расписания"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_schedule_{schedule_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_schedule_item_{schedule_id}"),
        ]
    ])

def student_delete_confirmation_keyboard(student_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления ученика"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"delete_student_confirmed_{student_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_student_{student_id}")
        ]
    ])

def schedule_modify_options_keyboard(schedule_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора того, что изменить в расписании"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 День недели", callback_data=f"modify_day_{schedule_id}"),
            InlineKeyboardButton(text="🕐 Время", callback_data=f"modify_time_{schedule_id}")
        ],
        [
            InlineKeyboardButton(text="📍 Формат", callback_data=f"modify_format_{schedule_id}"),
            InlineKeyboardButton(text="💰 Цена", callback_data=f"modify_price_{schedule_id}")
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"edit_schedule_item_{schedule_id}")]
    ])

def weekday_selection_for_edit_keyboard(schedule_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора дня недели для редактирования"""
    weekdays = [
        ("Понедельник", f"edit_weekday_0_{schedule_id}"),
        ("Вторник", f"edit_weekday_1_{schedule_id}"),
        ("Среда", f"edit_weekday_2_{schedule_id}"),
        ("Четверг", f"edit_weekday_3_{schedule_id}"),
        ("Пятница", f"edit_weekday_4_{schedule_id}"),
        ("Суббота", f"edit_weekday_5_{schedule_id}"),
        ("Воскресенье", f"edit_weekday_6_{schedule_id}")
    ]
    
    keyboard = []
    for day_name, callback_data in weekdays:
        keyboard.append([InlineKeyboardButton(text=day_name, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"edit_schedule_item_{schedule_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def lesson_format_edit_keyboard(schedule_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора формата для редактирования"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📍 Очно", callback_data=f"edit_format_offline_{schedule_id}")],
        [InlineKeyboardButton(text="💻 Онлайн", callback_data=f"edit_format_online_{schedule_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"edit_schedule_item_{schedule_id}")]
    ])

def lesson_format_selection_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора формата занятия"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📍 Очно", callback_data="format_offline")],
        [InlineKeyboardButton(text="💻 Онлайн", callback_data="format_online")]
    ])

def schedule_confirmation_keyboard(student_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения создания расписания"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Создать расписание", callback_data=f"confirm_schedule_{student_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"schedule_{student_id}")]
    ])

def back_to_admin_button() -> InlineKeyboardMarkup:
    """Кнопка назад в админ панель"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад в админ-панель", callback_data="back_to_admin")]
    ])

def price_settings_keyboard(has_settings: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура настроек цен"""
    buttons = []
    
    if has_settings:
        buttons.append([
            InlineKeyboardButton(text="✏️ Изменить базовую цену", callback_data="edit_price_base"),
            InlineKeyboardButton(text="✏️ Надбавка за онлайн", callback_data="edit_price_online")
        ])
        buttons.append([
            InlineKeyboardButton(text="✏️ Надбавка за 9 класс", callback_data="edit_price_grade_9"),
            InlineKeyboardButton(text="✏️ Надбавка за 10-11 класс", callback_data="edit_price_grade_10_11")
        ])
        buttons.append([
            InlineKeyboardButton(text="✏️ Надбавка за профиль", callback_data="edit_price_profile")
        ])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="back_to_admin")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def confirm_price_keyboard(price: float, student_id: int = None, lesson_id: int = None, is_lesson: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения цены при создании расписания/урока"""
    buttons = []
    
    if lesson_id:
        # Редактирование существующего урока
        buttons.append([InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_price_lesson_{student_id}_{lesson_id}")])
        buttons.append([InlineKeyboardButton(text="💰 Изменить цену", callback_data=f"change_price_lesson_{student_id}_{lesson_id}")])
    elif is_lesson:
        # Создание нового урока (lesson_id еще не существует)
        buttons.append([InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_new_lesson_price_{student_id}")])
        buttons.append([InlineKeyboardButton(text="💰 Изменить цену", callback_data=f"change_new_lesson_price_{student_id}")])
    else:
        # Создание расписания
        buttons.append([InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_price_schedule_{student_id}")])
        buttons.append([InlineKeyboardButton(text="💰 Изменить цену", callback_data=f"change_price_schedule_{student_id}")])
    
    if student_id:
        buttons.append([InlineKeyboardButton(text="◀️ Отмена", callback_data=f"view_student_{student_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def lesson_duration_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора продолжительности занятия"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🕐 1 час", callback_data="duration_60"),
            InlineKeyboardButton(text="🕐 1.5 часа", callback_data="duration_90")
        ],
        [
            InlineKeyboardButton(text="🕐 2 часа", callback_data="duration_120"),
            InlineKeyboardButton(text="✏️ Ввести свое", callback_data="duration_custom")
        ]
    ])

def lesson_duration_edit_keyboard(schedule_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора продолжительности для редактирования"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🕐 1 час", callback_data=f"edit_duration_60_{schedule_id}"),
            InlineKeyboardButton(text="🕐 1.5 часа", callback_data=f"edit_duration_90_{schedule_id}")
        ],
        [
            InlineKeyboardButton(text="🕐 2 часа", callback_data=f"edit_duration_120_{schedule_id}"),
            InlineKeyboardButton(text="✏️ Ввести свое", callback_data=f"edit_duration_custom_{schedule_id}")
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"edit_schedule_item_{schedule_id}")]
    ])

# Обновляем клавиатуру модификации расписания
def schedule_modify_options_keyboard(schedule_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора того, что изменить в расписании"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 День недели", callback_data=f"modify_day_{schedule_id}"),
            InlineKeyboardButton(text="🕐 Время", callback_data=f"modify_time_{schedule_id}")
        ],
        [
            InlineKeyboardButton(text="📍 Формат", callback_data=f"modify_format_{schedule_id}"),
            InlineKeyboardButton(text="💰 Цена", callback_data=f"modify_price_{schedule_id}")
        ],
        [
            InlineKeyboardButton(text="⏰ Продолжительность", callback_data=f"modify_duration_{schedule_id}")
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"edit_schedule_item_{schedule_id}")]
    ])

# Клавиатуры для уведомлений учителю
def lesson_ending_keyboard(lesson_id: int, student_id: Optional[int] = None) -> InlineKeyboardMarkup:
    """Клавиатура для уведомления о завершении занятия"""
    buttons = [
        [
            InlineKeyboardButton(text="💰 Оплачено", callback_data=f"payment_paid_{lesson_id}"),
            InlineKeyboardButton(text="❌ Не оплачено", callback_data=f"payment_unpaid_{lesson_id}")
        ],
        [InlineKeyboardButton(text="📝 Задать ДЗ", callback_data=f"add_homework_{lesson_id}")],
        [InlineKeyboardButton(text="✅ Занятие завершено", callback_data=f"lesson_complete_{lesson_id}")]
    ]

    if student_id:
        buttons.append([InlineKeyboardButton(text="👤 К профилю ученика", callback_data=f"view_student_{student_id}")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def lesson_confirmation_keyboard(lesson_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения участия в занятии (за 3 часа)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить участие", callback_data=f"confirm_attendance_{lesson_id}")]
    ])

def homework_actions_keyboard(lesson_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для действий с ДЗ"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ДЗ добавлено", callback_data=f"homework_added_{lesson_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"lesson_ending_{lesson_id}")]
    ])

# Клавиатуры для интерфейса "Мои занятия" учеников
def my_lessons_keyboard() -> InlineKeyboardMarkup:
    """Главное меню 'Мои занятия' для ученика"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔮 Предстоящие", callback_data="my_lessons_upcoming"),
            InlineKeyboardButton(text="📅 История", callback_data="my_lessons_history")
        ],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
    ])

def homework_list_keyboard(lessons: list, student_id: int, show_all: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для списка ДЗ с кнопками редактирования"""
    buttons = []
    
    # Добавляем кнопки для каждого занятия
    for lesson in lessons[:10]:
        date_str = format_date_with_weekday(lesson['lesson_date'], full_format=True)
        # Безопасная проверка наличия ДЗ
        homework = lesson.get('homework') or ''
        has_homework = bool(homework and homework.strip())
        
        if has_homework:
            # Если есть ДЗ, показываем дату + ✏️
            button_text = f"{date_str} ✏️"
        else:
            # Если нет ДЗ, показываем дату + ➕
            button_text = f"{date_str} ➕"
        
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"edit_homework_{lesson['id']}_{student_id}"
        )])
    
    # Добавляем кнопку возврата к профилю
    buttons.append([InlineKeyboardButton(
        text="◀️ К профилю",
        callback_data=f"view_student_{student_id}"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def homework_navigation_keyboard(student_id: int = None, show_all: bool = False, is_student: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для навигации по ДЗ"""
    buttons = []
    
    if is_student:
        # Для ученика - просто кнопка возврата в главное меню
        buttons.append([InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="back_to_main"
        )])
    else:
        # Для учителя - кнопки переключения и возврата к профилю
        if show_all:
            buttons.append([InlineKeyboardButton(
                text="📋 Показать только активные",
                callback_data=f"view_homework_{student_id}"
            )])
        else:
            buttons.append([InlineKeyboardButton(
                text="📚 Показать все ДЗ",
                callback_data=f"view_homework_all_{student_id}"
            )])
        
        buttons.append([InlineKeyboardButton(
            text="◀️ К профилю",
            callback_data=f"view_student_{student_id}"
        )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def student_homework_list_keyboard(lessons: list) -> InlineKeyboardMarkup:
    """Клавиатура со списком занятий для ученика"""
    from datetime import datetime
    
    buttons = []
    
    # Добавляем кнопки для каждого занятия (максимум 10)
    for lesson in lessons[:10]:
        # Форматируем дату без года
        try:
            date_obj = datetime.strptime(lesson['lesson_date'], '%Y-%m-%d')
            weekday = WEEKDAYS_RU[date_obj.weekday()]
            formatted_date = date_obj.strftime('%d.%m')
            date_str = f"{formatted_date} ({weekday})"
        except (ValueError, KeyError):
            date_str = lesson['lesson_date']
        
        has_homework = bool(lesson.get('homework') and lesson.get('homework').strip())
        emoji = "📝" if has_homework else "📅"
        button_text = f"{emoji} {date_str}"
        
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"student_homework_detail_{lesson['id']}"
        )])
    
    # Кнопка возврата в главное меню
    buttons.append([InlineKeyboardButton(
        text="🏠 Главное меню",
        callback_data="back_to_main"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def lesson_detail_keyboard(lesson_id: int) -> InlineKeyboardMarkup:
    """Детальная информация о занятии"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к списку", callback_data="back_to_my_lessons")]
    ])

def back_to_lessons_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата к списку занятий"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_my_lessons")]
    ])

# Клавиатуры для управления оплатой занятий (для учителя)
def payment_management_navigation(student_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """Навигация по страницам управления оплатой"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="◀️ Пред.", callback_data=f"pay_page_{student_id}_{page-1}"),
            InlineKeyboardButton(text="След. ▶️", callback_data=f"pay_page_{student_id}_{page+1}")
        ],
        [InlineKeyboardButton(text="👤 К профилю", callback_data=f"view_student_{student_id}")]
    ])

def lesson_payment_keyboard(lesson_id: int, student_id: int, current_status: str, lesson_status: str = 'scheduled') -> InlineKeyboardMarkup:
    """Клавиатура для изменения статуса оплаты и проведения конкретного занятия"""
    buttons = []
    
    # Первая строка: оплата и статус проведения
    first_row = []
    
    # Кнопка оплаты - показываем противоположную текущему статусу
    if current_status == 'paid':
        first_row.append(InlineKeyboardButton(text="❌ Отметить неоплаченным", callback_data=f"set_unpaid_{lesson_id}"))
    else:
        first_row.append(InlineKeyboardButton(text="✅ Отметить оплаченным", callback_data=f"set_paid_{lesson_id}"))
    
    # Кнопка для переключения статуса проведения
    if lesson_status == 'completed':
        first_row.append(InlineKeyboardButton(text="❌ Отметить не проведенным", callback_data=f"toggle_lesson_status_{lesson_id}"))
    else:
        first_row.append(InlineKeyboardButton(text="✅ Отметить проведенным", callback_data=f"toggle_lesson_status_{lesson_id}"))
    
    if first_row:
        buttons.append(first_row)
    
    # Вторая строка: кнопка "Задать ДЗ"
    buttons.append([InlineKeyboardButton(text="📝 Задать ДЗ", callback_data=f"add_homework_{lesson_id}")])

    # Третья строка: перенос занятия
    buttons.append([InlineKeyboardButton(text="🔄 Перенести занятие", callback_data=f"reschedule_lesson_{lesson_id}")])

    # Четвертая строка: удаление
    buttons.append([InlineKeyboardButton(text="🗑️ Удалить занятие", callback_data=f"confirm_delete_lesson_{lesson_id}")])

    # Пятая строка: назад
    buttons.append([InlineKeyboardButton(text="◀️ Назад к списку", callback_data=f"lessons_history_{student_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def student_changes_list_keyboard(students: List[Dict]) -> InlineKeyboardMarkup:
    """Клавиатура со списком учеников, которые меняли профиль"""
    buttons = []
    for student in students:
        buttons.append([
            InlineKeyboardButton(
                text=f"👤 {student['name']} ({student['changes_count']} изменений)",
                callback_data=f"student_changes_{student['user_id']}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_admin")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def student_changes_details_keyboard(student_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для деталей изменений ученика"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 К профилю ученика", callback_data=f"view_student_{student_id}")],
        [
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_admin"),
            InlineKeyboardButton(text="◀️ К изменениям", callback_data="show_student_changes")
        ]
    ])

def confirm_lesson_deletion_keyboard(lesson_id: int, student_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления занятия с выбором отправки уведомления"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📤 Удалить и уведомить", callback_data=f"delete_lesson_notify_{lesson_id}"),
            InlineKeyboardButton(text="🗑️ Удалить без уведомления", callback_data=f"delete_lesson_silent_{lesson_id}")
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_payment_{lesson_id}")
        ]
    ])

# Клавиатуры для раздела "Должники"
def debtors_list_keyboard(debtors: list) -> InlineKeyboardMarkup:
    """Клавиатура со списком должников"""
    buttons = []
    
    for debtor in debtors:
        debt_text = f"{debtor['name']} - {debtor['total_debt']:.0f}₽ ({debtor['unpaid_count']} занятий)"
        buttons.append([InlineKeyboardButton(
            text=debt_text,
            callback_data=f"debtor_details_{debtor['user_id']}"
        )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def debtor_details_keyboard(student_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для деталей должника"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Управление оплатой", callback_data=f"manage_payments_{student_id}")],
        [InlineKeyboardButton(text="👤 К профилю", callback_data=f"view_student_{student_id}")],
        [InlineKeyboardButton(text="◀️ К списку должников", callback_data="show_debtors")]
    ])

# Клавиатуры для фильтрации истории занятий (для учителя)
def history_filter_keyboard(student_id: int, current_filter: str = "smart") -> InlineKeyboardMarkup:
    """Клавиатура с фильтрами для истории занятий"""
    buttons = [
        [
            InlineKeyboardButton(
                text="🎯 Умный фильтр" if current_filter == "smart" else "⚪ Умный фильтр",
                callback_data=f"history_filter_smart_{student_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Только неоплаченные" if current_filter == "unpaid" else "⚪ Только неоплаченные",
                callback_data=f"history_filter_unpaid_{student_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="📅 Все занятия" if current_filter == "all" else "⚪ Все занятия",
                callback_data=f"history_filter_all_{student_id}"
            )
        ],
        [InlineKeyboardButton(text="👤 К профилю", callback_data=f"view_student_{student_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def lessons_with_filter_keyboard(student_id: int, lessons: list, current_filter: str = "smart") -> InlineKeyboardMarkup:
    """Клавиатура со списком занятий и кнопкой фильтра"""
    buttons = []
    
    # Добавляем кнопки для каждого занятия
    for lesson in lessons[:15]:  # Максимум 15 занятий
        date_str = format_date_with_weekday(lesson['lesson_date'])
        
        status_emoji = "✅" if lesson['status'] == 'completed' else "⏳"
        payment_emoji = "✅" if lesson['payment_status'] == 'paid' else "❌"
        
        button_text = f"{date_str} - {lesson['price']:.0f}₽ {status_emoji} {payment_emoji}"
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"edit_payment_{lesson['id']}"
        )])
    
    # Добавляем кнопку фильтра
    filter_texts = {
        "smart": "🎯 Фильтр: Умный",
        "unpaid": "❌ Фильтр: Неоплаченные",
        "all": "📅 Фильтр: Все"
    }
    buttons.append([InlineKeyboardButton(
        text=f"🔄 {filter_texts.get(current_filter, 'Фильтр')}",
        callback_data=f"change_history_filter_{student_id}"
    )])
    
    buttons.append([InlineKeyboardButton(text="👤 К профилю", callback_data=f"view_student_{student_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

#
#
# Проверить что клавиатуры работают.
#
#
# Клавиатура для заблокированных пользователей (подписка репетитора неактивна)
# subscription_expired = ReplyKeyboardMarkup(
#     keyboard=[
#         [KeyboardButton(text="💬 Связаться с репетитором")]
#     ],
#     resize_keyboard=True,
#     input_field_placeholder="Обратитесь к репетитору для возобновления"
# )

# # Дополнительная клавиатура для учеников - просмотр занятий
# student_lessons_keyboard = InlineKeyboardMarkup(inline_keyboard=[
#     [
#         InlineKeyboardButton(text="📅 Предстоящие", callback_data="lessons_upcoming"),
#         InlineKeyboardButton(text="📝 История", callback_data="lessons_history")
#     ],
#     [
#         InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")
#     ]
# ])

# # Клавиатура для репетиторов (админ-панель) - расширенная версия
# admin_main_extended = InlineKeyboardMarkup(inline_keyboard=[
#     [
#         InlineKeyboardButton(text="👨‍🎓 Мои ученики", callback_data="admin_students"),
#         InlineKeyboardButton(text="📅 Расписание", callback_data="admin_schedule")
#     ],
#     [
#         InlineKeyboardButton(text="➕ Записать ученика", callback_data="admin_book"),
#         InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")
#     ],
#     [
#         InlineKeyboardButton(text="💰 Управление ценами", callback_data="admin_prices"),
#         InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")
#     ]
# ])


# Клавиатуры для переноса занятия
def reschedule_date_keyboard(lesson_id: int, student_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для выбора новой даты занятия"""
    from datetime import datetime, timedelta

    buttons = []
    today = datetime.now()

    # Словарь для русских названий дней недели
    weekdays = {
        0: "Пн",
        1: "Вт",
        2: "Ср",
        3: "Чт",
        4: "Пт",
        5: "Сб",
        6: "Вс"
    }

    # Генерируем кнопки для ближайших 14 дней
    for i in range(1, 15):
        date = today + timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')
        weekday = weekdays[date.weekday()]
        display_text = f"{date.strftime('%d.%m')} ({weekday})"

        buttons.append([InlineKeyboardButton(
            text=display_text,
            callback_data=f"reschedule_date_{lesson_id}_{date_str}"
        )])

    # Кнопка отмены
    buttons.append([InlineKeyboardButton(
        text="❌ Отмена",
        callback_data=f"cancel_reschedule_{lesson_id}_{student_id}"
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def reschedule_time_keyboard(lesson_id: int, new_date: str, student_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для выбора нового времени занятия"""
    buttons = []

    # Популярные временные слоты
    times = [
        "08:00", "09:00", "10:00", "11:00",
        "12:00", "13:00", "14:00", "15:00",
        "16:00", "17:00", "18:00", "19:00",
        "20:00", "21:00"
    ]

    # Располагаем по 2 кнопки в ряд
    for i in range(0, len(times), 2):
        row = []
        for time in times[i:i+2]:
            row.append(InlineKeyboardButton(
                text=time,
                callback_data=f"reschedule_time_{lesson_id}_{new_date}_{time}"
            ))
        buttons.append(row)

    # Кнопка для ввода своего времени
    buttons.append([InlineKeyboardButton(
        text="⌨️ Ввести своё время",
        callback_data=f"reschedule_custom_time_{lesson_id}_{new_date}"
    )])

    # Кнопка возврата
    buttons.append([InlineKeyboardButton(
        text="◀️ К выбору даты",
        callback_data=f"reschedule_lesson_{lesson_id}"
    )])

    # Кнопка отмены
    buttons.append([InlineKeyboardButton(
        text="❌ Отмена",
        callback_data=f"cancel_reschedule_{lesson_id}_{student_id}"
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_reschedule_keyboard(lesson_id: int, student_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения переноса занятия"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить и уведомить", callback_data=f"confirm_reschedule_notify_{lesson_id}")
        ],
        [
            InlineKeyboardButton(text="✅ Подтвердить без уведомления", callback_data=f"confirm_reschedule_silent_{lesson_id}")
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_reschedule_{lesson_id}_{student_id}")
        ]
    ])


# === ИНЛАЙН-КАЛЕНДАРЬ ===

RUSSIAN_MONTHS = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}


def calendar_keyboard(
    year: int,
    month: int,
    context: str,
    extra_data: str = "",
    today_date: date | None = None
) -> InlineKeyboardMarkup:
    """
    Генерирует инлайн-клавиатуру с календарём на месяц.

    context: 'cl' (create_lesson) или 'rs' (reschedule)
    extra_data: доп. данные (напр. 's123', 'l456_s123')
    """
    if today_date is None:
        from bot_template.config import get_local_time
        today_date = get_local_time().date()

    cal = monthcalendar(year, month)
    buttons: list[list[InlineKeyboardButton]] = []

    # Заголовок месяца
    month_name = RUSSIAN_MONTHS[month]
    buttons.append([
        InlineKeyboardButton(text=f"{month_name} {year}", callback_data="cal_i")
    ])

    # Дни недели
    buttons.append([
        InlineKeyboardButton(text=day, callback_data="cal_i")
        for day in ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
    ])

    # Сетка дней
    for week in cal:
        row = []
        for day_num in week:
            if day_num == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="cal_i"))
            else:
                d = date(year, month, day_num)
                if d < today_date:
                    # Прошедший день — некликабельный
                    row.append(InlineKeyboardButton(text=" ", callback_data="cal_i"))
                elif d == today_date:
                    # Сегодня — подсвечиваем
                    cb = f"cal_d_{context}_{year}_{month}_{day_num}_{extra_data}"
                    row.append(InlineKeyboardButton(text=f"• {day_num} •", callback_data=cb))
                else:
                    # Будущий день
                    cb = f"cal_d_{context}_{year}_{month}_{day_num}_{extra_data}"
                    row.append(InlineKeyboardButton(text=str(day_num), callback_data=cb))
        buttons.append(row)

    # Навигация по месяцам
    prev_m = month - 1 if month > 1 else 12
    prev_y = year if month > 1 else year - 1
    next_m = month + 1 if month < 12 else 1
    next_y = year if month < 12 else year + 1

    current_month_first = date(today_date.year, today_date.month, 1)
    prev_month_first = date(prev_y, prev_m, 1)

    nav_row = []
    if prev_month_first >= current_month_first:
        nav_row.append(InlineKeyboardButton(
            text=f"◀ {RUSSIAN_MONTHS[prev_m]}",
            callback_data=f"cal_n_{context}_{prev_y}_{prev_m}_{extra_data}"
        ))
    else:
        nav_row.append(InlineKeyboardButton(text=" ", callback_data="cal_i"))

    nav_row.append(InlineKeyboardButton(
        text=f"{RUSSIAN_MONTHS[next_m]} ▶",
        callback_data=f"cal_n_{context}_{next_y}_{next_m}_{extra_data}"
    ))
    buttons.append(nav_row)

    # Кнопка "Назад"
    buttons.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"cal_b_{context}_{extra_data}")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
