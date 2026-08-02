import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.config import build_database_url, get_settings
from app.db.session import dispose_engine, init_engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    database_url = build_database_url(settings)
    init_engine(database_url, pool_size=settings.db_pool_size, max_overflow=settings.db_max_overflow)
    logger.info("Database engine initialized")

    yield

    await dispose_engine()


app = FastAPI(title="Arya API", version="0.1.0", lifespan=lifespan)

app.include_router(v1_router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
