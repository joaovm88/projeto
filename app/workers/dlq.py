"""Dead-Letter Queue: destino final de documentos cuja falha persistiu após todas
as tentativas de retry. Mantê-los visíveis (em vez de simplesmente descartá-los)
é o que garante rastreabilidade total do ciclo de vida do documento.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import redis

from app.core.config import get_settings

settings = get_settings()
_redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def send_to_dlq(document_id: str, error: str) -> None:
    payload = {
        "document_id": document_id,
        "error": error,
        "failed_at": datetime.now(UTC).isoformat(),
    }
    _redis_client.lpush(settings.dlq_key, json.dumps(payload))
