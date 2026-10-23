"""Таблицы базы данных: Users, Dishes, Orders, OrderItems (по схеме Этапа 2)."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# Роли пользователей
ROLE_STUDENT = "student"
ROLE_COOK = "cook"
ROLE_ADMIN = "admin"

# Статусы заказа: Новый -> Готовится -> Готов к выдаче -> Выдан
ORDER_STATUSES = ["new", "cooking", "ready", "issued"]


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=ROLE_STUDENT)
    balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)

    orders: Mapped[list["Order"]] = relationship(back_populates="user")


class Dish(Base):
    __tablename__ = "dishes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    category: Mapped[str] = mapped_column(String(50), index=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="new")
    pickup_time: Mapped[str] = mapped_column(String(50))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped[User] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    dish_id: Mapped[int] = mapped_column(ForeignKey("dishes.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    # Цена фиксируется на момент заказа, чтобы изменение меню не меняло старые заказы
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    order: Mapped[Order] = relationship(back_populates="items")
    dish: Mapped[Dish] = relationship()
