import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/notifications.db")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")