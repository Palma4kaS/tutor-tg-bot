import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS, API_PREFIX
from routers import student, teacher
from auth import get_current_user_with_bot
from schemas import RoleResponse

# Создаём приложение
app = FastAPI(
    title="Tutor Mini App API",
    description="API для Telegram Mini App репетитора",
    version="1.0.0",
    root_path="/api"
)

# Настраиваем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(student.router, prefix=API_PREFIX)
app.include_router(teacher.router, prefix=API_PREFIX)


@app.get("/me/role", response_model=RoleResponse)
async def get_my_role(
    user_with_bot=Depends(get_current_user_with_bot)
):
    """Определить роль пользователя: teacher или student"""
    role = "teacher" if user_with_bot.is_teacher else "student"
    return RoleResponse(role=role)


@app.get("/")
async def root():
    """Health check"""
    return {"status": "ok", "message": "Tutor Mini App API"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
