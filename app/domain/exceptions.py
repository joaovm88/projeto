class DocumentProcessingError(Exception):
    """Erro recuperável durante o processamento de um documento (dispara retry)."""
