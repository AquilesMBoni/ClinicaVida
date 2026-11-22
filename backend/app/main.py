"""Ponto de entrada da API da Clínica Vida.

Executar (a partir da pasta backend):   uvicorn app.main:app --reload
Site + API:  http://127.0.0.1:8000      Documentação: http://127.0.0.1:8000/docs
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import FRONTEND_DIR, settings
from .routers import appointments, assistant, catalog
from .seed import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    description="API do site demonstrativo da Clínica Vida: catálogo, pré-agendamento e assistente virtual.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^(null|http://(localhost|127\.0\.0\.1)(:\d+)?)$",   # file:// e servidores locais
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)


@app.exception_handler(RequestValidationError)
async def validation_handler(_request: Request, exc: RequestValidationError):
    """Devolve erros de validação como [{field, msg}] em português, prontos para o formulário."""
    errors = []
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", []) if p != "body"]
        msg = str(err.get("msg", "Valor inválido.")).removeprefix("Value error, ")
        errors.append({"field": loc[0] if loc else "", "msg": msg})
    return JSONResponse(status_code=422, content={"detail": errors})


@app.get("/api/health", tags=["infra"])
def health() -> dict:
    return {"status": "ok"}


app.include_router(catalog.router)
app.include_router(appointments.router)
app.include_router(assistant.router)

# Site estático servido pela própria API (mesma origem → sem CORS em produção)
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
