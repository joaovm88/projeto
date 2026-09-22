from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Document
from app.db.session import get_db
from app.schemas.document import (
    DocumentIngestRequest,
    DocumentIngestResponse,
    DocumentMetadata,
    DocumentStatus,
    DocumentStatusResponse,
)
from app.workers.tasks import process_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=DocumentIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def ingest_document(
    payload: DocumentIngestRequest, db: Session = Depends(get_db)
) -> DocumentIngestResponse:
    """O "garçom": recebe o pedido, anota e despacha para a cozinha (fila) sem bloquear."""
    if payload.idempotency_key:
        existing = (
            db.query(Document)
            .filter(Document.idempotency_key == payload.idempotency_key)
            .first()
        )
        if existing is not None:
            return DocumentIngestResponse(
                document_id=existing.id,
                status=DocumentStatus(existing.status),
                message="Documento já recebido anteriormente (idempotência).",
            )

    document = Document(
        raw_content=payload.raw_content,
        source=payload.source,
        idempotency_key=payload.idempotency_key,
        status=DocumentStatus.PENDING,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    process_document.delay(str(document.id))

    return DocumentIngestResponse(document_id=document.id, status=DocumentStatus.PENDING)


@router.get("/{document_id}", response_model=DocumentStatusResponse)
def get_document_status(
    document_id: uuid.UUID, db: Session = Depends(get_db)
) -> DocumentStatusResponse:
    """Permite consultar o status da "comanda" a qualquer instante."""
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    metadata = DocumentMetadata(**document.doc_metadata) if document.doc_metadata else None

    return DocumentStatusResponse(
        document_id=document.id,
        status=DocumentStatus(document.status),
        source=document.source,
        metadata=metadata,
        conteudo_limpo=document.cleaned_content,
        error_message=document.error_message,
        retry_count=document.retry_count,
        created_at=document.created_at,
        processed_at=document.processed_at,
    )
