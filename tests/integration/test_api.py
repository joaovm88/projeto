"""Teste de integração ponta a ponta: API -> banco real (via testcontainers).

O broker Celery é colocado em modo "eager" (execução síncrona in-process), o que
permite validar o fluxo completo de ingestão -> processamento -> persistência sem
precisar de um container de Redis/worker separado, mantendo o teste rápido e
determinístico, e ainda assim exercitando a lógica real de domínio e persistência.

Requer Docker disponível localmente; marcado com @pytest.mark.integration e
ignorado por padrão no CI de PRs (veja pytest -m "not integration").
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture()
def client(postgres_url: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", postgres_url.replace("postgresql://", "postgresql+psycopg2://"))
    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.core.celery_app import celery_app

    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)

    import importlib

    import app.db.session as session_module

    importlib.reload(session_module)
    session_module.init_db()

    from fastapi.testclient import TestClient

    import app.api.v1.documents as documents_module
    from app.main import app

    importlib.reload(documents_module)

    with TestClient(app) as test_client:
        yield test_client


def test_ingest_and_retrieve_document(client) -> None:
    response = client.post(
        "/api/v1/documents",
        json={
            "raw_content": (
                "Processo nº 0001234-56.2026.8.13.0707. Comarca de Varginha. "
                "Classe Judicial: Execução Fiscal. EXEQUENTE: Fazenda Pública. "
                "EXECUTADO: Empresa Comercial Ltda. Trata-se de penhora e intimação."
            ),
            "source": "DJE-TJMG",
        },
    )
    assert response.status_code == 202
    document_id = response.json()["document_id"]

    status_response = client.get(f"/api/v1/documents/{document_id}")
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["status"] == "PROCESSED"
    assert body["metadata"]["tribunal"] == "TJMG"
    assert body["metadata"]["numero_processo"] == "0001234-56.2026.8.13.0707"


def test_idempotency_key_prevents_duplicate_processing(client) -> None:
    payload = {
        "raw_content": "Texto suficientemente longo para ser aceito pela API.",
        "idempotency_key": "envio-123",
    }
    first = client.post("/api/v1/documents", json=payload)
    second = client.post("/api/v1/documents", json=payload)

    assert first.json()["document_id"] == second.json()["document_id"]


def test_unknown_document_returns_404(client) -> None:
    response = client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
