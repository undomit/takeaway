"""Application entry point: uvicorn app.main:app."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import create_api_router
from app.core.config import Settings, get_settings
from app.exception_handlers import register_exception_handlers
from app.health import router as health_router


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    # Validate before serving requests; importing the app never needs secrets or a DB.
    settings_provider = application.dependency_overrides.get(get_settings, get_settings)
    application.state.settings = settings_provider()
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    application = FastAPI(title="Takeaway API", version="0.1.0", lifespan=lifespan)
    if settings is not None:
        application.dependency_overrides[get_settings] = lambda: settings
    register_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(create_api_router())
    return application


app = create_app()
