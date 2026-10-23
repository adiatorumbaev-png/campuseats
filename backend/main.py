"""CampusEats — REST API сервера и раздача веб-интерфейса.

Запуск:  uvicorn backend.main:app --reload
Документация API (Swagger): http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .auth import create_token, get_current_user, hash_password, require_roles, verify_password
from .database import Base, SessionLocal, engine, get_db
from .schemas import (
    DishCreate, DishOut, DishUpdate, LoginIn, OrderCreate, OrderItemOut,
    OrderOut, RegisterIn, StatusUpdate, TokenOut, UserOut,
)
from .seed import seed

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # При запуске создаём таблицы и заполняем меню тестовыми данными
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="CampusEats API", version="1.0", lifespan=lifespan)

STAFF = (models.ROLE_COOK, models.ROLE_ADMIN)


def order_to_out(order: models.Order) -> OrderOut:
    return OrderOut(
        id=order.id,
        user_name=order.user.name,
        status=order.status,
        pickup_time=order.pickup_time,
        total_amount=float(order.total_amount),
        created_at=order.created_at,
        items=[
            OrderItemOut(dish_id=i.dish_id, title=i.dish.title,
                         quantity=i.quantity, price=float(i.price))
            for i in order.items
        ],
    )


# ---------- Авторизация ----------

@app.post("/api/auth/register", response_model=TokenOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    if db.scalar(select(models.User).where(models.User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Пользователь с таким email уже есть")
    user = models.User(
        name=data.name.strip(), email=email,
        password_hash=hash_password(data.password),
        role=models.ROLE_STUDENT, balance=Decimal("0"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenOut(token=create_token(user), user=UserOut.model_validate(user))


@app.post("/api/auth/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.email == data.email.strip().lower()))
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль")
    return TokenOut(token=create_token(user), user=UserOut.model_validate(user))


@app.get("/api/me", response_model=UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user


# ---------- Меню ----------

@app.get("/api/dishes", response_model=list[DishOut])
def list_dishes(category: str | None = None, db: Session = Depends(get_db)):
    query = select(models.Dish).order_by(models.Dish.category, models.Dish.title)
    if category:
        query = query.where(models.Dish.category == category)
    return db.scalars(query).all()


@app.post("/api/dishes", response_model=DishOut, status_code=201)
def create_dish(data: DishCreate, db: Session = Depends(get_db),
                _: models.User = Depends(require_roles(models.ROLE_ADMIN))):
    dish = models.Dish(**data.model_dump())
    db.add(dish)
    db.commit()
    db.refresh(dish)
    return dish


@app.patch("/api/dishes/{dish_id}", response_model=DishOut)
def update_dish(dish_id: int, data: DishUpdate, db: Session = Depends(get_db),
                _: models.User = Depends(require_roles(*STAFF))):
    dish = db.get(models.Dish, dish_id)
    if dish is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Блюдо не найдено")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(dish, field, value)
    db.commit()
    db.refresh(dish)
    return dish


# ---------- Заказы ----------

@app.post("/api/orders", response_model=OrderOut, status_code=201)
def create_order(data: OrderCreate, db: Session = Depends(get_db),
                 user: models.User = Depends(get_current_user)):
    # 1. Проверяем, что все блюда существуют и есть в наличии
    total = Decimal("0")
    items = []
    unavailable = []
    for cart_item in data.items:
        dish = db.get(models.Dish, cart_item.dish_id)
        if dish is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Блюдо #{cart_item.dish_id} не найдено")
        if not dish.is_available:
            unavailable.append({"id": dish.id, "title": dish.title, "category": dish.category})
            continue
        total += dish.price * cart_item.quantity
        items.append(models.OrderItem(dish_id=dish.id, quantity=cart_item.quantity, price=dish.price))

    # Exception flow 5.1: блюдо закончилось во время оформления
    if unavailable:
        raise HTTPException(status.HTTP_409_CONFLICT, {
            "message": "Некоторые блюда закончились",
            "unavailable": unavailable,
        })

    # Exception flow 5.2: не хватает средств на балансе
    if user.balance < total:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, {
            "message": "Недостаточно средств на балансе",
            "balance": float(user.balance),
            "total": float(total),
        })

    # 2. Списываем деньги и сохраняем заказ (одной транзакцией)
    user.balance -= total
    order = models.Order(user_id=user.id, pickup_time=data.pickup_time,
                         total_amount=total, status="new", items=items)
    db.add(order)
    db.commit()
    db.refresh(order)
    return order_to_out(order)


@app.get("/api/orders/my", response_model=list[OrderOut])
def my_orders(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    orders = db.scalars(
        select(models.Order).where(models.Order.user_id == user.id)
        .order_by(models.Order.created_at.desc())
    ).all()
    return [order_to_out(o) for o in orders]


@app.get("/api/orders", response_model=list[OrderOut])
def all_orders(active_only: bool = True, db: Session = Depends(get_db),
               _: models.User = Depends(require_roles(*STAFF))):
    query = select(models.Order).order_by(models.Order.pickup_time, models.Order.created_at)
    if active_only:
        query = query.where(models.Order.status != "issued")
    return [order_to_out(o) for o in db.scalars(query).all()]


@app.patch("/api/orders/{order_id}/status", response_model=OrderOut)
def change_status(order_id: int, data: StatusUpdate, db: Session = Depends(get_db),
                  _: models.User = Depends(require_roles(*STAFF))):
    if data.status not in models.ORDER_STATUSES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Неизвестный статус")
    order = db.get(models.Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Заказ не найден")
    order.status = data.status
    db.commit()
    db.refresh(order)
    return order_to_out(order)


# ---------- Администратор: пополнение баланса ----------

class TopUpByEmail(BaseModel):
    email: str
    amount: float = Field(gt=0, le=100000)


@app.post("/api/admin/topup", response_model=UserOut)
def top_up(data: TopUpByEmail, db: Session = Depends(get_db),
           _: models.User = Depends(require_roles(models.ROLE_ADMIN))):
    user = db.scalar(select(models.User).where(models.User.email == data.email.strip().lower()))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    user.balance += Decimal(str(data.amount))
    db.commit()
    db.refresh(user)
    return user


# ---------- Веб-интерфейс ----------

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND_DIR / "index.html")
