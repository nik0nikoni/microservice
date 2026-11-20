import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from . import models  # noqa: F401
from .consumer import consume_forever, state
from .db import Base, engine
from .routes import router

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "service": "notification-service", '
    '"level": "%(levelname)s", "message": "%(message)s"}',
)

Base.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # потребитель работает в фоновом потоке рядом с веб-сервером
    threading.Thread(target=consume_forever, daemon=True, name="rabbit-consumer").start()
    yield


app = FastAPI(title="notification-service", version="1.0.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Database unavailable")
    if not state["connected"]:
        raise HTTPException(503, "RabbitMQ consumer not connected")
    return {"status": "ready"}