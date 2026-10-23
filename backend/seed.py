"""Начальные данные: тестовые пользователи и меню столовой."""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import hash_password
from .models import Dish, ROLE_ADMIN, ROLE_COOK, ROLE_STUDENT, User

TEST_USERS = [
    ("Студент Тестовый", "student@campus.kz", "student123", ROLE_STUDENT, "5000"),
    ("Повар Столовой", "cook@campus.kz", "cook123", ROLE_COOK, "0"),
    ("Администратор", "admin@campus.kz", "admin123", ROLE_ADMIN, "0"),
]

MENU = [
    ("Борщ", "900", "Первые блюда"),
    ("Сорпа", "850", "Первые блюда"),
    ("Куриный суп с лапшой", "800", "Первые блюда"),
    ("Плов", "1200", "Вторые блюда"),
    ("Лагман", "1300", "Вторые блюда"),
    ("Манты (4 шт.)", "1100", "Вторые блюда"),
    ("Котлета с пюре", "1000", "Вторые блюда"),
    ("Салат «Витаминный»", "500", "Салаты"),
    ("Салат «Оливье»", "600", "Салаты"),
    ("Самса с мясом", "400", "Выпечка"),
    ("Пирожок с картошкой", "250", "Выпечка"),
    ("Баурсаки (5 шт.)", "300", "Выпечка"),
    ("Чай", "150", "Напитки"),
    ("Компот", "250", "Напитки"),
    ("Кофе 3 в 1", "300", "Напитки"),
]


def seed(db: Session) -> None:
    """Заполняет БД, только если она пустая."""
    if db.scalar(select(User).limit(1)) is None:
        for name, email, password, role, balance in TEST_USERS:
            db.add(User(name=name, email=email, password_hash=hash_password(password),
                        role=role, balance=Decimal(balance)))
    if db.scalar(select(Dish).limit(1)) is None:
        for title, price, category in MENU:
            db.add(Dish(title=title, price=Decimal(price), category=category, is_available=True))
    db.commit()
