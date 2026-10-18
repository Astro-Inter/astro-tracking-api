"""Resolve o IP do evento sem confiar em headers de proxy na execução local."""

from ipaddress import ip_address

from fastapi import Request


def resolver_cliente_ip(request: Request, informado=None):
    # O binding env é acrescentado pelo adaptador ASGI do Cloudflare Workers.
    # Fora do Worker, CF-Connecting-IP e X-Forwarded-For não são confiáveis.
    if request.scope.get("env") is not None:
        for name in ("CF-Connecting-IPv6", "CF-Connecting-IP"):
            value = request.headers.get(name)
            if value and "%" not in value:
                try:
                    return ip_address(value.strip())
                except ValueError:
                    continue
    return informado
