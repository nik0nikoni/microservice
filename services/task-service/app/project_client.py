import logging

import httpx
from fastapi import HTTPException

from .config import PROJECT_SERVICE_URL

logger = logging.getLogger("task-service")


def get_membership(project_id: int, user_id: int, request_id: str | None = None) -> dict | None:
    """Синхронный вызов project-service: состоит ли пользователь в проекте.

    Возвращает {"user_id": .., "role": ..} или None, если не состоит.
    """
    headers = {"X-Request-ID": request_id} if request_id else {}
    url = f"{PROJECT_SERVICE_URL}/internal/projects/{project_id}/members/{user_id}"
    try:
        response = httpx.get(url, headers=headers, timeout=3.0)
    except httpx.RequestError:
        logger.error("project-service unreachable: request_id=%s", request_id)
        raise HTTPException(503, "Project service unavailable")

    if response.status_code == 200:
        return response.json()
    if response.status_code == 404:
        return None
    logger.error("project-service returned %s", response.status_code)
    raise HTTPException(502, "Project service error")