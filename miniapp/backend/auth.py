import hmac
import hashlib
import json
import logging
from urllib.parse import parse_qsl, unquote
from typing import Optional
from datetime import datetime

from fastapi import HTTPException, Header, Depends
from pydantic import BaseModel

from config import BOT_TOKEN, BOTS_CONFIG, get_admins_for_tutor

# Настраиваем логирование
logger = logging.getLogger(__name__)


class TelegramUser(BaseModel):
    """Данные пользователя из Telegram WebApp"""
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None
    is_premium: Optional[bool] = None


class TelegramUserWithBot(BaseModel):
    """Данные пользователя с информацией о боте"""
    user: TelegramUser
    bot_token: str
    tutor_folder: str
    admins_ids: list[int] = []

    @property
    def is_teacher(self) -> bool:
        return self.user.id in self.admins_ids


def validate_init_data(init_data: str, bot_token: str) -> TelegramUser:
    """
    Валидация initData из Telegram WebApp.

    Args:
        init_data: Строка initData из Telegram.WebApp.initData
        bot_token: Токен бота для проверки подписи

    Returns:
        TelegramUser: Данные пользователя

    Raises:
        ValueError: Если данные невалидны или подпись неверна
    """
    if not init_data:
        raise ValueError("Empty init data")

    # Парсим данные
    parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))

    # Извлекаем hash
    received_hash = parsed_data.pop('hash', None)
    if not received_hash:
        raise ValueError("Hash not found in init data")

    # Формируем строку для проверки (сортируем по ключам)
    data_check_string = '\n'.join(
        f"{k}={v}" for k, v in sorted(parsed_data.items())
    )

    # Вычисляем HMAC
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256
    ).digest()

    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    # Проверяем подпись
    if calculated_hash != received_hash:
        raise ValueError("Invalid hash")

    # Проверяем время (auth_date не старше 24 часов)
    auth_date = parsed_data.get('auth_date')
    if auth_date:
        auth_timestamp = int(auth_date)
        current_timestamp = int(datetime.now().timestamp())
        if current_timestamp - auth_timestamp > 86400:  # 24 часа
            raise ValueError("Init data expired")

    # Извлекаем данные пользователя
    user_data = parsed_data.get('user')
    if not user_data:
        raise ValueError("User data not found")

    try:
        user_dict = json.loads(unquote(user_data))
        return TelegramUser(**user_dict)
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueError(f"Invalid user data: {e}")


def validate_init_data_multi_tenant(init_data: str) -> TelegramUserWithBot:
    """
    Валидация initData с поддержкой нескольких ботов.
    Пробует все токены из BOTS_CONFIG и возвращает данные пользователя с информацией о боте.

    Args:
        init_data: Строка initData из Telegram.WebApp.initData

    Returns:
        TelegramUserWithBot: Данные пользователя с информацией о боте

    Raises:
        ValueError: Если данные невалидны для всех ботов
    """
    if not BOTS_CONFIG:
        raise ValueError("No bots configured in BOTS_CONFIG")

    errors = []

    # Пробуем валидировать со всеми токенами
    for bot_token, tutor_folder in BOTS_CONFIG.items():
        try:
            user = validate_init_data(init_data, bot_token)
            logger.info(f"Successfully validated with bot for tutor: {tutor_folder}")
            return TelegramUserWithBot(
                user=user,
                bot_token=bot_token,
                tutor_folder=tutor_folder,
                admins_ids=get_admins_for_tutor(tutor_folder)
            )
        except ValueError as e:
            errors.append(f"{tutor_folder}: {str(e)}")
            continue

    # Если ни один токен не подошёл
    raise ValueError(f"Failed to validate with any bot. Errors: {'; '.join(errors)}")


async def get_current_user(
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data")
) -> TelegramUser:
    """
    Dependency для получения текущего пользователя из заголовка X-Telegram-Init-Data.
    Оставлен для обратной совместимости.

    Usage:
        @app.get("/api/profile")
        async def get_profile(user: TelegramUser = Depends(get_current_user)):
            ...
    """
    user_with_bot = await get_current_user_with_bot(x_telegram_init_data)
    return user_with_bot.user


async def get_current_user_with_bot(
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data")
) -> TelegramUserWithBot:
    """
    Dependency для получения текущего пользователя с информацией о боте.
    Использует multi-tenant валидацию.

    Usage:
        @app.get("/api/profile")
        async def get_profile(user_with_bot: TelegramUserWithBot = Depends(get_current_user_with_bot)):
            ...
    """
    logger.info(f"Auth attempt - initData present: {bool(x_telegram_init_data)}")

    if not x_telegram_init_data:
        logger.warning("Missing Telegram init data")
        raise HTTPException(
            status_code=401,
            detail="Missing Telegram init data"
        )

    if not BOTS_CONFIG:
        logger.error("No bots configured")
        raise HTTPException(
            status_code=500,
            detail="No bots configured"
        )

    try:
        user_with_bot = validate_init_data_multi_tenant(x_telegram_init_data)
        logger.info(f"User authenticated successfully: user_id={user_with_bot.user.id}, "
                   f"username={user_with_bot.user.username}, tutor={user_with_bot.tutor_folder}")
        return user_with_bot
    except ValueError as e:
        logger.warning(f"Failed to validate init data: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail=f"Invalid Telegram init data: {str(e)}"
        )


async def get_current_teacher(
    user_with_bot: TelegramUserWithBot = Depends(get_current_user_with_bot)
) -> TelegramUserWithBot:
    """
    Dependency для учительской панели.
    Проверяет, что user_id входит в список администраторов тутора.
    """
    if not user_with_bot.is_teacher:
        raise HTTPException(
            status_code=403,
            detail="Доступ запрещён: только для учителей"
        )
    return user_with_bot


# Для разработки: заглушка, которая не проверяет подпись
async def get_current_user_dev(
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
    x_dev_user_id: Optional[int] = Header(None, alias="X-Dev-User-Id")
) -> TelegramUser:
    """
    Development-версия авторизации.
    Позволяет передать X-Dev-User-Id для тестирования без Telegram.
    """
    if x_dev_user_id:
        return TelegramUser(
            id=x_dev_user_id,
            first_name="Dev User"
        )

    return await get_current_user(x_telegram_init_data)
