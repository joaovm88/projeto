from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação, carregadas de variáveis de ambiente (.env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"

    database_url: str = "postgresql+psycopg2://docpipeline:docpipeline@localhost:5432/docpipeline"

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    redis_url: str = "redis://localhost:6379/0"

    max_retries: int = 3
    retry_backoff_seconds: int = 2

    dlq_key: str = "dlq:documents"


@lru_cache
def get_settings() -> Settings:
    return Settings()
