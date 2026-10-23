"""Схемы запросов и ответов API (Pydantic)."""
from datetime import datetime

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=100)
    password: str = Field(min_length=6, max_length=72)


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    balance: float

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    token: str
    user: UserOut


class DishOut(BaseModel):
    id: int
    title: str
    price: float
    category: str
    is_available: bool

    model_config = {"from_attributes": True}


class DishCreate(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    price: float = Field(gt=0)
    category: str = Field(min_length=2, max_length=50)
    is_available: bool = True


class DishUpdate(BaseModel):
    title: str | None = None
    price: float | None = Field(default=None, gt=0)
    category: str | None = None
    is_available: bool | None = None


class CartItem(BaseModel):
    dish_id: int
    quantity: int = Field(ge=1, le=20)


class OrderCreate(BaseModel):
    items: list[CartItem] = Field(min_length=1)
    pickup_time: str = Field(min_length=1, max_length=50)


class OrderItemOut(BaseModel):
    dish_id: int
    title: str
    quantity: int
    price: float


class OrderOut(BaseModel):
    id: int
    user_name: str
    status: str
    pickup_time: str
    total_amount: float
    created_at: datetime
    items: list[OrderItemOut]


class StatusUpdate(BaseModel):
    status: str


class TopUpIn(BaseModel):
    amount: float = Field(gt=0, le=100000)
