import logging

from asyncpg import PostgresError
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings, get_settings
from .routes import router


logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()
    app = FastAPI(
        title="Astro — API de Tracking", version="2.0.0",
        description="dataLayer → GTM → API → PostgreSQL. Horários em UTC.",
    )
    app.state.config = config
    app.add_middleware(
        CORSMiddleware, allow_origins=config.cors_origins,
        allow_credentials=False, allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    async def database_error(request: Request, exc: Exception):
        logger.error("Falha de persistência: %s", type(exc).__name__)
        return JSONResponse(status_code=503, content={"detail": "Banco indisponível ou estrutura incompatível."})

    for error in (PostgresError, OSError, TimeoutError):
        app.add_exception_handler(error, database_error)

    app.include_router(router)
    return app
