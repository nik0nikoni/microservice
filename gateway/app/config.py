import os

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")

# префикс пути -> адрес сервиса; новые сервисы добавляются сюда
ROUTES = [
    ("/api/auth", AUTH_SERVICE_URL),
]

# пути, которые доступны без токена
PUBLIC_PATHS = {"/api/auth/register", "/api/auth/login"}