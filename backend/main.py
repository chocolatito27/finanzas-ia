"""FinanzasIA — punto de entrada del backend.

Levantar en local:
    .venv\\Scripts\\python -m uvicorn main:app --reload --port 8000

Documentación interactiva: http://localhost:8000/docs
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from routers import admin, archivos, auth, movimientos

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("finanzas-ia")


@asynccontextmanager
async def lifespan(app: FastAPI):
    faltantes = settings.validar()
    if faltantes:
        logger.warning(
            "Faltan variables de entorno (%s). Revisa backend/.env",
            ", ".join(faltantes),
        )
    else:
        logger.info(
            "Configuración OK — modelo IA: %s | Supabase: %s",
            settings.venice_model, settings.supabase_url,
        )
    yield


app = FastAPI(
    title="FinanzasIA API",
    description="Procesa estados de cuenta bancarios y genera el dashboard financiero.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def error_no_controlado(request: Request, exc: Exception) -> JSONResponse:
    """Evita filtrar stack traces al cliente; el detalle queda en los logs."""
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Ocurrió un error inesperado. Intenta de nuevo."},
    )


@app.get("/", tags=["salud"])
async def raiz() -> dict:
    return {"servicio": "FinanzasIA API", "version": "1.0.0", "docs": "/docs"}


@app.get("/api/salud", tags=["salud"])
async def salud() -> dict:
    """Health check: útil para Railway/Render y para depurar la configuración."""
    faltantes = settings.validar()
    return {
        "ok": not faltantes,
        "variables_faltantes": faltantes,
        "modelo_ia": settings.venice_model,
    }


@app.get("/api/config-publica", tags=["salud"])
async def config_publica() -> dict:
    """Datos no sensibles que el frontend necesita (número de WhatsApp)."""
    return {"whatsapp_number": settings.whatsapp_number}


@app.post("/api/diagnostico", tags=["salud"])
async def guardar_diagnostico(datos: dict, request: Request) -> dict:
    """Recibe el registro de la página /diagnostico.

    **Temporal.** Existe porque un fallo del selector de archivos que solo ocurre
    en Chrome de Android no se puede reproducir en escritorio, y sin datos del
    dispositivo real cada arreglo es una adivinanza. Cuando el problema esté
    cerrado, borrar esto y la tabla `diagnosticos`.

    Es público a propósito: hay que poder usarlo desde el celular sin pelear con
    la sesión. Solo guarda lo que el propio navegador reporta de sí mismo.
    """
    from database import get_client

    registro = datos.get("registro")
    if not isinstance(registro, list):
        registro = []

    try:
        get_client().table("diagnosticos").insert(
            {
                "agente": str(datos.get("agente") or "")[:1000],
                "pantalla": str(datos.get("pantalla") or "")[:200],
                "tactil": bool(datos.get("tactil")),
                # Se recorta: es un diagnóstico, no un almacén de eventos
                "registro": registro[:200],
            }
        ).execute()
    except Exception:
        logger.exception("No se pudo guardar el diagnóstico")
        raise HTTPException(500, "No se pudo guardar el diagnóstico")

    logger.info(
        "Diagnóstico recibido de %s — %s eventos",
        str(datos.get("agente"))[:120], len(registro),
    )
    return {"ok": True, "eventos_guardados": len(registro[:200])}


app.include_router(auth.router)
app.include_router(archivos.router)
app.include_router(movimientos.router)
app.include_router(admin.router)
