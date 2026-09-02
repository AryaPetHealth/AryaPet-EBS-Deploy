import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

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


@app.get("/swagger.html", include_in_schema=False)
async def swagger_html() -> HTMLResponse:
    # Same Swagger UI FastAPI already serves at /docs, just under a URL some people
    # find more memorable to link/bookmark against the EB environment.
    return get_swagger_ui_html(openapi_url=app.openapi_url, title=f"{app.title} - Swagger UI")
