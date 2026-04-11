from .common import router, db, send_lesson_start_notification

# Import all handler modules to trigger handler registration
from . import admin
from . import schedule
from . import lessons
from . import homework
from . import student
