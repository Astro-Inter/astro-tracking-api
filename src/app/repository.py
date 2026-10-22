from asyncpg import Connection

from .schemas import EventoCreate


INSERT_EVENTO = """
    INSERT INTO evento_astro (
        firebase_uid, tipo_evento, nome_botao, nome_tela, contexto_tela,
        nome_dialog, dialog_clicado, showcase_click, nome_showcase, cliente_ip, criado_em
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::inet, CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
    RETURNING id_evento, firebase_uid, tipo_evento, nome_botao, nome_tela,
              contexto_tela, nome_dialog, dialog_clicado, showcase_click,
              nome_showcase, cliente_ip, criado_em
"""


async def criar_evento(db: Connection, dados: EventoCreate) -> dict:
    # Uma instrução atômica; não depende de PK ou DEFAULT de criado_em na tabela.
    registro = await db.fetchrow(
        INSERT_EVENTO,
        dados.firebase_uid, dados.tipo_evento, dados.nome_botao, dados.nome_tela,
        dados.contexto_tela, dados.nome_dialog, dados.dialog_clicado,
        dados.showcase_click, dados.nome_showcase, dados.cliente_ip,
    )
    return dict(registro)
