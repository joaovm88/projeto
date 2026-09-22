from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class DocumentStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class DocumentIngestRequest(BaseModel):
    raw_content: str = Field(..., min_length=10, description="Texto bruto a ser processado")
    source: str | None = Field(
        default=None, max_length=255, description="Origem do documento (ex.: 'DJE-TJMG')"
    )
    idempotency_key: str | None = Field(
        default=None,
        max_length=255,
        description="Chave opcional para evitar reprocessamento de um mesmo envio",
    )


class DocumentIngestResponse(BaseModel):
    document_id: uuid.UUID
    status: DocumentStatus
    message: str = "Documento recebido para processamento assíncrono."


class DocumentMetadata(BaseModel):
    numero_processo: str | None = None
    tribunal: str | None = None
    comarca: str | None = None
    classe_judicial: str | None = None
    data_publicacao: str | None = None
    partes_identificadas: dict[str, str | None] = Field(default_factory=dict)
    palavras_chave: list[str] = Field(default_factory=list)


class DocumentStatusResponse(BaseModel):
    document_id: uuid.UUID
    status: DocumentStatus
    source: str | None = None
    metadata: DocumentMetadata | None = None
    conteudo_limpo: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    created_at: datetime
    processed_at: datetime | None = None
