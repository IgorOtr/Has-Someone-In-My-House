"""Ponto de composição da aplicação FastAPI do painel web.

Processo separado e opcional do monitor (``run.py``): não abre a webcam,
não roda inferência e não controla o monitor diretamente — só monta os
routers (``web/routers``), o middleware de segurança, o ciclo de vida
(criação/migração do banco no startup) e o front-end estático.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from web.db import ensure_database_exists, ensure_schema_migrations, init_models
from web.dependencies import get_auth_settings, get_engine, get_person_detector
from web.routers import (
    alerts_router,
    auth_router,
    detections_router,
    monitor_router,
    webcam_router,
)

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Prepara o banco de dados (cria/migra) uma vez, no startup do servidor."""
    auth_settings = get_auth_settings()
    if auth_settings.uses_insecure_default_secret:
        logger.warning(
            "JWT_SECRET_KEY is using its insecure default value. Set a real "
            "secret in .env before exposing this dashboard beyond localhost."
        )
    ensure_database_exists(auth_settings)
    engine = get_engine()
    init_models(engine)
    ensure_schema_migrations(engine)

    # Carrega o YOLO11n já no startup, para a primeira sessão de webcam do
    # navegador não pagar esse custo. Best-effort: se falhar (ex.: modelo
    # ausente e sem internet para baixar), só desativa a webcam do
    # navegador — o resto do dashboard continua funcionando normalmente.
    try:
        get_person_detector()
    except Exception:
        logger.warning(
            "Browser webcam monitoring is disabled: could not load the YOLO model.",
            exc_info=True,
        )

    yield


app = FastAPI(title="Person Detection Monitor API", lifespan=lifespan)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Adiciona headers básicos de segurança em toda resposta da API."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


app.include_router(auth_router.router)
app.include_router(detections_router.router)
app.include_router(alerts_router.router)
app.include_router(monitor_router.router)
app.include_router(webcam_router.router)

# Serve o front-end estático (index/login/register/alerts + JS) na raiz.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
