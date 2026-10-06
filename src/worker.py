from functools import lru_cache

import json
from urllib.parse import unquote

from workers import asgi, fetch

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
    status = 500

    async def capture_response(message):
        nonlocal status
        if message.get("type") == "http.response.start":
            status = int(message.get("status", 500))
        await send(message)

    try:
        await app(scope, receive, capture_response)
    except Exception as error:
        await _export_log(env, scope, 500, error.__class__.__name__)
        raise
    await _export_log(env, scope, status)


async def _export_log(env, scope, status, reason=None):
    if env is None:
        return
    endpoint = getattr(env, "GRAFANA_OTLP_ENDPOINT", None)
    raw_headers = getattr(env, "GRAFANA_OTLP_HEADERS", None)
    if not endpoint or not raw_headers:
        return
    headers = {"Content-Type": "application/json"}
    try:
        for pair in str(raw_headers).split(","):
            name, separator, value = pair.partition("=")
            if separator and name.strip():
                headers[name.strip()] = unquote(value.strip())
        base = str(endpoint).rstrip("/")
        url = base if base.endswith("/v1/logs") else f"{base}/v1/logs"
        event = "http_request_failed" if status >= 500 else "http_request_completed"
        attributes = [
            {"key": "event.name", "value": {"stringValue": event}},
            {"key": "http.request.method", "value": {"stringValue": str(scope.get("method", "UNKNOWN"))}},
            {"key": "http.response.status_code", "value": {"intValue": str(status)}},
        ]
        if reason:
            attributes.append({"key": "error.type", "value": {"stringValue": reason}})
        payload = {"resourceLogs": [{"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "astro-tracking-api"}}]}, "scopeLogs": [{"scope": {"name": "astro-cloudflare-logs", "version": "1"}, "logRecords": [{"timeUnixNano": str(__import__("time").time_ns()), "severityNumber": 17 if status >= 500 else 9, "severityText": "ERROR" if status >= 500 else "INFO", "body": {"stringValue": event}, "attributes": attributes}]}]}]}
        response = await fetch(url, method="POST", headers=headers, body=json.dumps(payload))
        if not response.ok:
            print(json.dumps({"event": "grafana_export_failed", "status": response.status}))
    except Exception:
        print(json.dumps({"event": "grafana_export_failed", "reason": "network_or_timeout"}))


Default = asgi.entrypoint(application)
