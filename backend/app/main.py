import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1 import activities, auth, care, links, media, notifications, product, wellbeing
from app.core.config import settings
from app.db.session import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("memorycare")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.storage_root.resolve().mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:80]
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled API error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "An internal server error occurred"})


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "memorycare-api"}


@app.get("/health/ready", tags=["health"])
def readiness() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ready", "database": "connected"}


prefix = settings.api_v1_prefix.rstrip("/")
for route_module in (auth, links, notifications, care, activities, media, product, wellbeing):
    app.include_router(route_module.router, prefix=prefix)
