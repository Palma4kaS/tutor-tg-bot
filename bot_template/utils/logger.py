"""
Модуль логирования для Tutor Bot.

Обеспечивает:
- Консольный вывод (INFO и выше)
- Файловый лог с ротацией (DEBUG и выше)
- Отдельный файл для ошибок
"""

import logging
import logging.handlers
import os
from typing import Optional


def setup_logging(
    log_dir: str = "logs",
    tutor_id: Optional[str] = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG
) -> logging.Logger:
    """
    Инициализирует систему логирования.

    Args:
        log_dir: Директория для файлов логов
        tutor_id: ID репетитора для именования файлов
        console_level: Уровень логирования в консоль
        file_level: Уровень логирования в файл

    Returns:
        Настроенный logger
    """
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("tutor_bot")

    # Избегаем дублирования handlers при повторных вызовах
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Формат сообщений
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler с ротацией (основной лог)
    log_filename = f"bot_{tutor_id}.log" if tutor_id else "bot.log"
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, log_filename),
        maxBytes=10_485_760,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Error File Handler (только ошибки)
    error_filename = f"bot_{tutor_id}_errors.log" if tutor_id else "bot_errors.log"
    error_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, error_filename),
        maxBytes=10_485_760,  # 10 MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Получить logger для модуля.

    Args:
        name: Имя модуля (обычно __name__)

    Returns:
        Logger с указанным именем
    """
    if name:
        return logging.getLogger(f"tutor_bot.{name}")
    return logging.getLogger("tutor_bot")
