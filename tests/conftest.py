import os
import time
import uuid

import httpx
import pytest

BASE_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=10) as c:
        yield c


def make_user(client: httpx.Client, prefix: str = "user") -> dict:
    """Регистрирует нового пользователя и логинится. Возвращает id, email и заголовки с токеном."""
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"
    password = "password123"

    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    user_id = r.json()["id"]

    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    return {
        "id": user_id,
        "email": email,
        "password": password,
        "headers": {"Authorization": f"Bearer {token}"},
    }


def wait_for(fn, timeout: float = 10.0, interval: float = 0.5):
    """Повторяет fn, пока она не вернёт что-то непустое (нужно для асинхронных событий)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = fn()
        if result:
            return result
        time.sleep(interval)
    return fn()