import os

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")


USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://localhost:8002")
PROJECT_SERVICE_URL = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8003")
TASK_SERVICE_URL = os.getenv("TASK_SERVICE_URL", "http://localhost:8004")

ROUTES = [
    ("/api/auth", AUTH_SERVICE_URL),
    ("/api/users", USER_SERVICE_URL),
    ("/api/projects", PROJECT_SERVICE_URL),
    ("/api/tasks", TASK_SERVICE_URL),
]

# пути, которые доступны без токена
PUBLIC_PATHS = {"/api/auth/register", "/api/auth/login"}