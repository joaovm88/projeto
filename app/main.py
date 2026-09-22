from fastapi import FastAPI

from app.api.v1.router import api_router
from app.db.session import init_db

app = FastAPI(
    title="DocPipeline",
    description=(
        "Pipeline assíncrono de ingestão, sanitização e estruturação de documentos "
        "jurídicos em larga escala."
    ),
    version="0.1.0",
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router)
