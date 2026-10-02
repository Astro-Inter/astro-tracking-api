"""Verifica a aplicação ASGI com bindings simulados; não executa workerd."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient


def test_worker_cors_bindings_e_lifespan(monkeypatch):
    # O SDK depende de JS/Pyodide, indisponível no CPython usado pelos testes.
    import sys
    sdk = SimpleNamespace(asgi=SimpleNamespace(entrypoint=lambda application: application))
    monkeypatch.setitem(sys.modules, "workers", sdk)
    spec = importlib.util.spec_from_file_location("worker_test", Path(__file__).resolve().parents[1] / "src" / "worker.py")
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)

    env = SimpleNamespace(CORS_ALLOWED_ORIGINS="https://frontend.example")

    async def with_bindings(scope, receive, send):
        if scope["type"] == "http":
            scope = dict(scope, env=env)
        await worker.application(scope, receive, send)

    # TestClient também executa lifespan sem env, como o adaptador oficial.
    with TestClient(with_bindings) as client:
        assert client.get("/health").status_code == 200
        headers = {"Origin": env.CORS_ALLOWED_ORIGINS, "Access-Control-Request-Method": "POST"}
        response = client.options("/api/eventos", headers=headers)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == env.CORS_ALLOWED_ORIGINS
        env.CORS_ALLOWED_ORIGINS = "https://outro.example"
        assert client.options("/api/eventos", headers=headers).status_code == 400

    assert worker.worker_app("https://frontend.example") is worker.worker_app("https://frontend.example")
