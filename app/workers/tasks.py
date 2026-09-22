from __future__ import annotations

import uuid
from datetime import UTC, datetime

from celery.exceptions import MaxRetriesExceededError

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.db.models import Document
from app.db.session import SessionLocal
from app.domain.exceptions import DocumentProcessingError
from app.domain.parser import extract_metadata, sanitize
from app.schemas.document import DocumentStatus
from app.workers.dlq import send_to_dlq

settings = get_settings()


@celery_app.task(bind=True, max_retries=settings.max_retries, name="documents.process_document")
def process_document(self, document_id: str) -> None:
    """O "cozinheiro": retira a comanda da fila e executa o processamento pesado.

    É idempotente (reexecutar sobre o mesmo document_id apenas reprocessa o mesmo
    conteúdo bruto e sobrescreve o resultado) e resiliente (retries com backoff
    exponencial; após esgotar as tentativas, o documento vai para a DLQ).
    """
    db = SessionLocal()
    try:
        document = db.get(Document, uuid.UUID(document_id))
        if document is None:
            return

        document.status = DocumentStatus.PROCESSING
        db.commit()

        try:
            cleaned = sanitize(document.raw_content)
            metadata = extract_metadata(document.raw_content)
        except Exception as exc:  # falha ao processar -> candidata a retry
            raise DocumentProcessingError(str(exc)) from exc

        document.cleaned_content = cleaned
        document.doc_metadata = metadata
        document.status = DocumentStatus.PROCESSED
        document.processed_at = datetime.now(UTC)
        db.commit()

    except DocumentProcessingError as exc:
        db.rollback()
        document = db.get(Document, uuid.UUID(document_id))
        if document:
            document.retry_count += 1
            db.commit()

        try:
            countdown = settings.retry_backoff_seconds**self.request.retries
            raise self.retry(exc=exc, countdown=countdown)
        except MaxRetriesExceededError:
            document = db.get(Document, uuid.UUID(document_id))
            if document:
                document.status = DocumentStatus.FAILED
                document.error_message = str(exc)
                db.commit()
            send_to_dlq(document_id, str(exc))
    finally:
        db.close()
