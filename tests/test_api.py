import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import asyncpg
import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import get_db
from app.main import create_app


EVENTOS = {
    "screen_view": {},
    "button_click": {"nome_botao": "entrar"},
    "dialog_viewed": {"nome_dialog": "convite"},
    "dialog_clicked": {"nome_dialog": "convite", "dialog_clicado": "confirmar"},
    "showcase_viewed": {"nome_showcase": "inicio"},
    "showcase_clicked": {"nome_showcase": "inicio", "showcase_click": "proximo"},
    "conversation_started": {},
    "conversation_message_sent": {},
    "conversation_message_received": {},
}


@pytest.fixture
def banco(monkeypatch):
    db = AsyncMock()

    async def salvar(query, *values):
        columns = ("firebase_uid", "tipo_evento", "nome_botao", "nome_tela", "contexto_tela",
                   "nome_dialog", "dialog_clicado", "showcase_click", "nome_showcase")
        return dict(zip(columns, values), id_evento=1, criado_em=datetime(2026, 10, 2, 12))

    db.fetchrow.side_effect = salvar
    connect = AsyncMock(return_value=db)
    monkeypatch.setattr(asyncpg, "connect", connect)
    return db, connect


@pytest.fixture
def client(banco):
    app = create_app(Settings(db_password="teste", _env_file=None))
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("tipo,campos", EVENTOS.items())
@pytest.mark.parametrize("uid", [None, "firebase-usuario"])
def test_eventos(client, banco, tipo, campos, uid):
    payload = dict(tipo_evento=tipo, firebase_uid=uid, nome_tela="login", **campos)
    response = client.post("/api/eventos", json=payload)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert all(saved[key] == value for key, value in payload.items())
    assert saved["criado_em"] == "2026-10-02T12:00:00Z"
    assert saved["id_evento"] == 1
    banco[0].close.assert_awaited_once()


@pytest.mark.parametrize("field", ["id_evento", "criado_em", "event", "gtm.uniqueEventId", "mensagem"])
def test_campos_extras_sem_conectar(client, banco, field):
    response = client.post("/api/eventos", json={"tipo_evento": "screen_view", field: None})
    assert response.status_code == 422
    banco[1].assert_not_awaited()


@pytest.mark.parametrize("tipo,campos", EVENTOS.items())
def test_campos_obrigatorios(client, banco, tipo, campos):
    for field in campos:
        payload = dict(tipo_evento=tipo, **campos)
        del payload[field]
        assert client.post("/api/eventos", json=payload).status_code == 422
    banco[1].assert_not_awaited()


@pytest.mark.parametrize("field", ["nome_botao", "nome_showcase", "showcase_click"])
def test_evento_nao_mistura_componentes(client, banco, field):
    payload = dict(tipo_evento="dialog_clicked", **EVENTOS["dialog_clicked"], **{field: "indevido"})
    assert client.post("/api/eventos", json=payload).status_code == 422
    banco[0].fetchrow.assert_not_awaited()


@pytest.mark.parametrize("value", [None, True, "", "   "])
def test_clique_exige_texto(client, value):
    assert client.post("/api/eventos", json={
        "tipo_evento": "dialog_clicked", "nome_dialog": "convite", "dialog_clicado": value,
    }).status_code == 422


@pytest.mark.parametrize("payload", [{}, {"tipo_evento": "desconhecido"},
    {"tipo_evento": "screen_view", "contexto_tela": "x" * 8001},
    {"tipo_evento": "screen_view", "firebase_uid": ""}])
def test_contrato_invalido(client, banco, payload):
    assert client.post("/api/eventos", json=payload).status_code == 422
    banco[1].assert_not_awaited()


@pytest.mark.parametrize("field", ["nome_tela", "contexto_tela", "firebase_uid"])
def test_nul_rejeitado_antes_do_postgres(client, banco, field):
    assert client.post("/api/eventos", json={"tipo_evento": "screen_view", field: "abc\u0000def"}).status_code == 422
    banco[1].assert_not_awaited()


def test_sql_parametrizado_e_horario_sem_default(client, banco):
    malicious = "'); DROP TABLE eventos_astro; --"
    response = client.post("/api/eventos", json={"tipo_evento": "screen_view", "nome_tela": malicious})
    assert response.status_code == 201
    query, *values = banco[0].fetchrow.call_args.args
    assert malicious not in query
    assert malicious in values
    assert "CURRENT_TIMESTAMP AT TIME ZONE 'UTC'" in query
    assert "RETURNING id_evento" in query


@pytest.mark.parametrize("error", [asyncpg.UndefinedTableError("segredo"), OSError("segredo"), TimeoutError("segredo")])
@pytest.mark.parametrize("stage", ["connect", "insert"])
def test_falha_banco_nao_confirma_evento(client, banco, error, stage):
    (banco[1] if stage == "connect" else banco[0].fetchrow).side_effect = error
    response = client.post("/api/eventos", json={"tipo_evento": "screen_view"})
    assert response.status_code == 503
    assert "segredo" not in response.text
    if stage == "insert":
        banco[0].close.assert_awaited_once()


def test_health_e_api_apenas_ingestao(client, banco):
    assert client.get("/health").json() == {"status": "ok"}
    banco[1].assert_not_awaited()
    assert client.get("/api/eventos").status_code == 405
    assert client.get("/api/eventos/1").status_code == 404
    assert client.get("/health/db").status_code == 200
    assert "firebase_uid" in banco[0].execute.call_args.args[0]


def test_cors(client):
    headers = {"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
               "Access-Control-Request-Headers": "content-type"}
    response = client.options("/api/eventos", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == headers["Origin"]
    headers["Origin"] = "https://outro.example"
    assert client.options("/api/eventos", headers=headers).status_code == 400


def test_cors_em_erro_banco(client, banco):
    banco[1].side_effect = TimeoutError()
    response = client.post("/api/eventos", json={"tipo_evento": "screen_view"}, headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 503
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_hyperdrive_sem_lifespan(banco):
    hd = SimpleNamespace(host="proxy", port="5432", user="user", password="senha", database="astro")
    request = Request({"type": "http", "env": SimpleNamespace(HYPERDRIVE=hd)})

    async def scenario():
        async with get_db(request):
            pass

    asyncio.run(scenario())
    options = banco[1].call_args.kwargs
    assert options["host"] == "proxy"
    assert options["ssl"] is False
    assert options["statement_cache_size"] == 0
    banco[0].close.assert_awaited_once()
