from datetime import datetime, timezone
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Nome = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Tipo = Literal["screen_view", "button_click", "dialog_viewed", "dialog_clicked", "showcase_viewed", "showcase_clicked", "conversation_started", "conversation_message_sent", "conversation_message_received"]

class CamposEvento(BaseModel):
    """Campos recebidos do GTM e devolvidos na confirmação de gravação."""
    model_config = ConfigDict(extra="forbid")
    firebase_uid: Nome | None = None
    tipo_evento: str
    nome_tela: Nome | None = None
    contexto_tela: str | None = Field(default=None, max_length=8_000)
    nome_botao: Nome | None = None
    nome_dialog: Nome | None = None
    dialog_clicado: Nome | None = None
    nome_showcase: Nome | None = None
    showcase_click: Nome | None = None

    @field_validator("*")
    @classmethod
    def texto_sem_nul(cls, value):
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("Texto não pode conter caractere NUL")
        return value

class EventoCreate(CamposEvento):
    """Valida um POST e exige os nomes associados ao evento escolhido."""
    tipo_evento: Tipo
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "tipo_evento": "dialog_clicked", "nome_tela": "gestor", "contexto_tela": "gestor",
        "nome_botao": None, "nome_dialog": "convidar_gestor", "dialog_clicado": "convidar",
        "nome_showcase": None, "showcase_click": None
    }]})

    @model_validator(mode="after")
    def validar_campos_do_evento(self):
        permitidos = {
            "button_click": {"nome_botao"},
            "dialog_viewed": {"nome_dialog"},
            "dialog_clicked": {"nome_dialog", "dialog_clicado"},
            "showcase_viewed": {"nome_showcase"},
            "showcase_clicked": {"nome_showcase", "showcase_click"},
        }.get(self.tipo_evento, set())
        for campo in {"nome_botao", "nome_dialog", "dialog_clicado", "nome_showcase", "showcase_click"}:
            value = getattr(self, campo)
            if campo not in permitidos and value is not None:
                raise ValueError(f"{campo} deve ser null para {self.tipo_evento}")
            if campo in permitidos and value is None:
                raise ValueError(f"{campo} é obrigatório para {self.tipo_evento}")
        return self

class EventoRead(CamposEvento):
    id_evento: int
    criado_em: datetime

    @field_validator("criado_em")
    @classmethod
    def horario_utc(cls, value: datetime) -> datetime:
        # TIMESTAMP não carrega timezone; o INSERT grava UTC explicitamente.
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
