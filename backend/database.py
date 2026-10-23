"""Подключение к базе данных.

По умолчанию используется SQLite (файл campuseats.db), чтобы проект запускался
без установки сервера БД. Для PostgreSQL достаточно задать переменную окружения:
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/campuseats
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./campuseats.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """Открывает сессию БД на время одного запроса."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
