from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from fastapi import Request


@asynccontextmanager
async def get_db(request: Request) -> AsyncIterator[asyncpg.Connection]:
    env = request.scope.get("env")
    if env is not None:
        hd = env.HYPERDRIVE
        # Hyperdrive gerencia o pool. A conexão pertence somente a esta requisição.
        options = dict(
            host=hd.host, port=int(hd.port), user=hd.user,
            password=hd.password, database=hd.database, ssl=False,
        )
    else:
        config = request.app.state.config
        options = dict(
            host=config.db_host, port=config.db_port, user=config.db_user,
            password=config.db_password.get_secret_value(), database=config.db_name,
            ssl=config.db_ssl,
        )
    db = await asyncpg.connect(**options, timeout=5, command_timeout=10, statement_cache_size=0)
    try:
        yield db
    finally:
        await db.close(timeout=5)
