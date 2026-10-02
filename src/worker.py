from functools import lru_cache

from workers import asgi

from app.config import Settings
from app.main import create_app


@lru_cache(maxsize=4)
def worker_app(origins: str):
    config = Settings(
        _env_file=None, db_password="",
        cors_allowed_origins=origins,
    )
    return create_app(config)


async def application(scope, receive, send):
    # Os bindings são fornecidos pelo ASGI do Workers, sem depender de .env/lifespan.
    env = scope.get("env")
    app = worker_app(str(env.CORS_ALLOWED_ORIGINS) if env is not None else "")
    await app(scope, receive, send)


Default = asgi.entrypoint(application)
