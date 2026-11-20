import logging
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager

import httpx
import jwt
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from .config import (
    AUTH_SERVICE_URL,
    JWT_ALGORITHM,
    JWT_SECRET,
    PUBLIC_PATHS,
    RATE_LIMIT_PER_MINUTE,
    ROUTES,
)

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "service": "gateway", '
    '"level": "%(levelname)s", "message": "%(message)s"}',
)
logger = logging.getLogger("gateway")

HOP_HEADERS = {
    "host", "content-length", "connection", "transfer-encoding", "keep-alive",
    "upgrade", "te", "trailer", "proxy-authorization", "proxy-authenticate",
}

_hits: dict[str, deque] = defaultdict(deque)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient(timeout=10.0)
    yield
    await app.state.client.aclose()


app = FastAPI(title="api-gateway", version="1.0.0", lifespan=lifespan)


def is_rate_limited(key: str) -> bool:
    now = time.monotonic()
    window = _hits[key]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= RATE_LIMIT_PER_MINUTE:
        return True
    window.append(now)
    return False


def find_upstream(path: str) -> str | None:
    for prefix, url in ROUTES:
        if path == prefix or path.startswith(prefix + "/"):
            return url
    return None


def verify_token(request: Request) -> dict:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Missing bearer token")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready(request: Request):
    try:
        r = await request.app.state.client.get(f"{AUTH_SERVICE_URL}/health")
        r.raise_for_status()
    except Exception:
        raise HTTPException(503, "Upstream unavailable")
    return {"status": "ready"}


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request):
    started = time.monotonic()
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    full_path = "/api/" + path
    client_ip = request.client.host if request.client else "unknown"

    def respond(status: int, detail: str) -> JSONResponse:
        logger.info(
            "%s %s -> %s %.0fms request_id=%s",
            request.method, full_path, status,
            (time.monotonic() - started) * 1000, request_id,
        )
        return JSONResponse(
            {"detail": detail}, status_code=status,
            headers={"X-Request-ID": request_id},
        )

    if is_rate_limited(client_ip):
        return respond(429, "Too many requests")

    user_headers: dict[str, str] = {}
    if full_path not in PUBLIC_PATHS:
        try:
            claims = verify_token(request)
        except HTTPException as e:
            return respond(e.status_code, e.detail)
        user_headers = {"X-User-Id": str(claims["sub"]), "X-User-Email": claims.get("email", "")}

    upstream_base = find_upstream(full_path)
    if upstream_base is None:
        return respond(404, "Route not found")

    # убираем заголовки X-User-*, пришедшие от клиента: их ставит только gateway
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in HOP_HEADERS and not k.lower().startswith("x-user-")
    }
    headers.update(user_headers)
    headers["X-Request-ID"] = request_id

    try:
        upstream = await request.app.state.client.request(
            request.method,
            upstream_base + full_path,
            params=request.query_params,
            headers=headers,
            content=await request.body(),
        )
    except httpx.TimeoutException:
        return respond(504, "Upstream timeout")
    except httpx.RequestError:
        return respond(502, "Upstream unavailable")

    logger.info(
        "%s %s -> %s %.0fms request_id=%s",
        request.method, full_path, upstream.status_code,
        (time.monotonic() - started) * 1000, request_id,
    )
    out_headers = {
        k: v for k, v in upstream.headers.items()
        if k.lower() not in HOP_HEADERS and k.lower() != "content-encoding"
    }
    out_headers["X-Request-ID"] = request_id
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=out_headers,
    )