"""Integração opt-in: somente um banco de testes explicitamente configurado."""

import asyncio
import os
import uuid

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL não configurada")
def test_tabela_exata_sem_pk_ou_default_timestamp(monkeypatch):
    url = os.environ["TEST_DATABASE_URL"]
    schema = "test_astro_" + uuid.uuid4().hex
    original_connect = asyncpg.connect

    async def setup():
        db = await original_connect(url)
        try:
            await db.execute(f'CREATE SCHEMA "{schema}"')
            await db.execute(f"""CREATE TABLE "{schema}".eventos_astro (
                id_evento BIGSERIAL,
                firebase_uid VARCHAR,
                tipo_evento VARCHAR,
                nome_botao VARCHAR,
                nome_tela VARCHAR,
                contexto_tela TEXT,
                nome_dialog VARCHAR,
                dialog_clicado VARCHAR,
                showcase_click VARCHAR,
                nome_showcase VARCHAR,
                criado_em TIMESTAMP
            )""")
        finally:
            await db.close()

    async def cleanup():
        db = await original_connect(url)
        try:
            await db.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        finally:
            await db.close()

    async def test_connection(**kwargs):
        return await original_connect(url, server_settings={"search_path": schema}, statement_cache_size=0)

    try:
        asyncio.run(setup())
        monkeypatch.setattr(asyncpg, "connect", test_connection)
        app = create_app(Settings(db_password="teste", _env_file=None))
        with TestClient(app) as client:
            assert client.get("/health/db").status_code == 200
            first = client.post("/api/eventos", json={"tipo_evento": "screen_view"})
            second = client.post("/api/eventos", json={"tipo_evento": "button_click", "nome_botao": "entrar", "firebase_uid": "uid-teste"})
            assert first.status_code == second.status_code == 201
            assert first.json()["firebase_uid"] is None
            assert second.json()["id_evento"] > first.json()["id_evento"]
            assert first.json()["criado_em"].endswith("Z")

        async def check_saved():
            db = await test_connection()
            try:
                rows = await db.fetch("SELECT * FROM eventos_astro ORDER BY id_evento")
                assert len(rows) == 2
                assert rows[1]["firebase_uid"] == "uid-teste"
                assert rows[0]["criado_em"] is not None
            finally:
                await db.close()

        asyncio.run(check_saved())
    finally:
        asyncio.run(cleanup())
