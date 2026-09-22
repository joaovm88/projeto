import pytest
from pydantic import ValidationError

from app.schemas.document import DocumentIngestRequest, DocumentStatus


class TestDocumentIngestRequest:
    def test_accepts_valid_payload(self) -> None:
        request = DocumentIngestRequest(raw_content="Texto com conteúdo suficiente.")
        assert request.source is None
        assert request.idempotency_key is None

    def test_rejects_too_short_content(self) -> None:
        with pytest.raises(ValidationError):
            DocumentIngestRequest(raw_content="curto")


class TestDocumentStatus:
    def test_status_values(self) -> None:
        assert set(DocumentStatus) == {
            DocumentStatus.PENDING,
            DocumentStatus.PROCESSING,
            DocumentStatus.PROCESSED,
            DocumentStatus.FAILED,
        }
