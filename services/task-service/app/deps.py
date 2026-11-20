from fastapi import Header, HTTPException


def current_user(
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
) -> dict:
    """Данные пользователя приходят от gateway в заголовках."""
    if not x_user_id or not x_user_id.isdigit():
        raise HTTPException(401, "Missing user identity")
    return {"id": int(x_user_id), "email": x_user_email or ""}


def request_id(x_request_id: str | None = Header(default=None)) -> str | None:
    """Сквозной id запроса от gateway, передаём его дальше и в события."""
    return x_request_id