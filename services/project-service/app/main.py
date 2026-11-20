import logging

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from . import models  # noqa: F401
from .db import Base, engine
from .routes import internal, router

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "service": "project-service", '
    '"level": "%(levelname)s", "message": "%(message)s"}',
)

Base.metadata.create_all(engine)

app = FastAPI(title="project-service", version="1.0.0")
app.include_router(router)
app.include_router(internal)


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
    return {"status": "ready"}