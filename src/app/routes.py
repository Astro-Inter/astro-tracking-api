from fastapi import APIRouter, Request, status

from .client_ip import resolver_cliente_ip
from .database import get_db
from .repository import criar_evento
from .schemas import EventoCreate, EventoRead


router = APIRouter()


@router.post("/api/eventos", response_model=EventoRead, status_code=status.HTTP_201_CREATED, tags=["Eventos"])
async def receber_evento(dados: EventoCreate, request: Request):
    dados = dados.model_copy(update={
        "cliente_ip": resolver_cliente_ip(request, dados.cliente_ip),
    })
    async with get_db(request) as db:
        return await criar_evento(db, dados)


@router.get("/health", tags=["Saúde"])
async def health():
    return {"status": "ok"}


@router.get("/health/db", tags=["Saúde"])
async def health_db(request: Request):
    async with get_db(request) as db:
        await db.execute("SELECT id_evento, firebase_uid, cliente_ip, tipo_evento, nome_botao, nome_tela, contexto_tela, nome_dialog, dialog_clicado, showcase_click, nome_showcase, criado_em FROM eventos_astro LIMIT 0")
    return {"status": "ok", "banco": "conectado", "tabela": "eventos_astro"}
