"""Тесты API. Запуск: python -m pytest -v"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import pytest
from fastapi.testclient import TestClient

from backend.database import Base, engine
from backend.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:  # при старте создаются таблицы и тестовые данные
        yield c
    Base.metadata.drop_all(bind=engine)


def login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_register_and_login(client):
    r = client.post("/api/auth/register", json={"name": "Адият", "email": "a@campus.kz", "password": "secret1"})
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "student"
    assert client.post("/api/auth/login", json={"email": "a@campus.kz", "password": "wrong!"}).status_code == 401
    login(client, "a@campus.kz", "secret1")


def test_dishes_filter_by_category(client):
    dishes = client.get("/api/dishes", params={"category": "Напитки"}).json()
    assert dishes and all(d["category"] == "Напитки" for d in dishes)


def test_order_main_flow_and_total(client):
    student = login(client, "student@campus.kz", "student123")
    dishes = {d["title"]: d for d in client.get("/api/dishes").json()}
    items = [{"dish_id": dishes["Плов"]["id"], "quantity": 2},   # 2 × 1200
             {"dish_id": dishes["Чай"]["id"], "quantity": 1}]    # 1 × 150
    r = client.post("/api/orders", json={"items": items, "pickup_time": "11:40"}, headers=student)
    assert r.status_code == 201
    assert r.json()["total_amount"] == 2550
    assert client.get("/api/me", headers=student).json()["balance"] == 5000 - 2550

    # повар меняет статус
    cook = login(client, "cook@campus.kz", "cook123")
    order_id = r.json()["id"]
    r = client.patch(f"/api/orders/{order_id}/status", json={"status": "ready"}, headers=cook)
    assert r.json()["status"] == "ready"
    # студент не может менять статус
    assert client.patch(f"/api/orders/{order_id}/status", json={"status": "issued"}, headers=student).status_code == 403


def test_exception_dish_unavailable(client):
    student = login(client, "student@campus.kz", "student123")
    admin = login(client, "admin@campus.kz", "admin123")
    dish = client.get("/api/dishes").json()[0]
    client.patch(f"/api/dishes/{dish['id']}", json={"is_available": False}, headers=admin)
    r = client.post("/api/orders", json={"items": [{"dish_id": dish["id"], "quantity": 1}], "pickup_time": "11:40"}, headers=student)
    assert r.status_code == 409
    assert r.json()["detail"]["unavailable"][0]["id"] == dish["id"]
    # деньги не списались
    assert client.get("/api/me", headers=student).json()["balance"] == 5000


def test_exception_not_enough_money(client):
    student = login(client, "student@campus.kz", "student123")
    dish = client.get("/api/dishes").json()[0]
    r = client.post("/api/orders", json={"items": [{"dish_id": dish["id"], "quantity": 20}], "pickup_time": "11:40"}, headers=student)
    assert r.status_code == 402


def test_order_requires_login(client):
    assert client.post("/api/orders", json={"items": [{"dish_id": 1, "quantity": 1}], "pickup_time": "x"}).status_code == 401
