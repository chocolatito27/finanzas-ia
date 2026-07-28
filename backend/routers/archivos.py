"""Subida y procesamiento de estados de cuenta.

Flujo por archivo:
    bytes → extractor (PDF o Excel) → IA (categorización) → Supabase

Cada archivo se procesa de forma independiente: si uno falla, los demás siguen y el
frontend recibe el detalle de qué pasó con cada uno.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from database import (
    buscar_archivo_por_hash,
    eliminar_archivo,
    listar_archivos,
    insertar_movimientos,
    obtener_perfil,
    registrar_archivo,
)
from models import ArchivoResultado, SubidaRespuesta
from security import UsuarioAutenticado, descifrar_clave, usuario_activo
from services.excel_extractor import extraer_movimientos_excel
from services.ia_categorizer import categorizar_movimientos
from services.pdf_extractor import ErrorExtraccion, extraer_movimientos_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/archivos", tags=["archivos"])

EXTENSIONES_PDF = (".pdf",)
EXTENSIONES_EXCEL = (".xlsx", ".xlsm", ".xls", ".csv")
MAX_BYTES = 15 * 1024 * 1024      # 15 MB por archivo
MAX_ARCHIVOS = 12                 # por request


async def _procesar_uno(
    user_id: str, nombre: str, contenido: bytes, clave_pdf: str | None
) -> ArchivoResultado:
    nombre_bajo = nombre.lower()

    if len(contenido) > MAX_BYTES:
        return ArchivoResultado(
            nombre_archivo=nombre, ok=False, codigo_error="MUY_GRANDE",
            error=f"El archivo pesa más de {MAX_BYTES // (1024 * 1024)} MB.",
        )

    if not nombre_bajo.endswith(EXTENSIONES_PDF + EXTENSIONES_EXCEL):
        return ArchivoResultado(
            nombre_archivo=nombre, ok=False, codigo_error="FORMATO_NO_SOPORTADO",
            error="Solo se aceptan archivos PDF, Excel (.xlsx) o CSV.",
        )

    # Evita reprocesar y duplicar movimientos si el usuario sube el mismo archivo dos veces
    hash_archivo = hashlib.sha256(contenido).hexdigest()
    ya_existe = buscar_archivo_por_hash(user_id, hash_archivo)
    if ya_existe:
        return ArchivoResultado(
            nombre_archivo=nombre, ok=False, codigo_error="DUPLICADO",
            error="Este archivo ya fue procesado antes; no se volvió a cargar.",
            banco_detectado=ya_existe.get("banco_detectado"),
        )

    # --- 1. Extracción (bloqueante: va a un hilo para no frenar el event loop) ---
    try:
        if nombre_bajo.endswith(EXTENSIONES_PDF):
            extraccion = await asyncio.to_thread(
                extraer_movimientos_pdf, contenido, clave_pdf
            )
        else:
            extraccion = await asyncio.to_thread(
                extraer_movimientos_excel, contenido, nombre
            )
    except ErrorExtraccion as exc:
        logger.info("Extracción falló para '%s': %s", nombre, exc.mensaje)
        return ArchivoResultado(
            nombre_archivo=nombre, ok=False, codigo_error=exc.codigo, error=exc.mensaje
        )
    except Exception as exc:
        logger.exception("Error inesperado extrayendo '%s'", nombre)
        return ArchivoResultado(
            nombre_archivo=nombre, ok=False, codigo_error="ERROR_INTERNO",
            error=f"No se pudo leer el archivo: {exc}",
        )

    # --- 2. Categorización con la IA ---
    categorizados = await categorizar_movimientos(extraccion.movimientos)

    # --- 3. Persistencia ---
    try:
        archivo = registrar_archivo(
            user_id=user_id,
            nombre_archivo=nombre,
            hash_archivo=hash_archivo,
            banco=extraccion.banco,
            mes_inicio=extraccion.mes_inicio,
            mes_fin=extraccion.mes_fin,
            total_movimientos=len(categorizados),
        )
        insertados = insertar_movimientos(user_id, archivo["id"], categorizados)
    except Exception as exc:
        logger.exception("Error guardando '%s' en la base de datos", nombre)
        return ArchivoResultado(
            nombre_archivo=nombre, ok=False, codigo_error="ERROR_BD",
            error=f"No se pudieron guardar los movimientos: {exc}",
        )

    return ArchivoResultado(
        nombre_archivo=nombre,
        ok=True,
        banco_detectado=extraccion.banco,
        movimientos_insertados=insertados,
        mes_inicio=extraccion.mes_inicio,
        mes_fin=extraccion.mes_fin,
    )


@router.post("/subir", response_model=SubidaRespuesta)
async def subir_archivos(
    archivos: list[UploadFile] = File(...),
    usuario: UsuarioAutenticado = Depends(usuario_activo),
) -> SubidaRespuesta:
    """Sube y procesa uno o varios estados de cuenta.

    Puede tardar 30–60 s: el frontend debe mostrar un loading.
    """
    if not archivos:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No se envió ningún archivo")
    if len(archivos) > MAX_ARCHIVOS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Máximo {MAX_ARCHIVOS} archivos por vez.",
        )

    perfil = obtener_perfil(usuario.id) or {}
    clave_pdf = descifrar_clave(perfil.get("clave_pdf"))

    resultados: list[ArchivoResultado] = []
    for archivo in archivos:
        contenido = await archivo.read()
        nombre = archivo.filename or "archivo_sin_nombre"
        resultados.append(await _procesar_uno(usuario.id, nombre, contenido, clave_pdf))

    total = sum(r.movimientos_insertados for r in resultados)
    logger.info(
        "Usuario %s subió %s archivo(s): %s movimientos nuevos",
        usuario.id, len(archivos), total,
    )
    return SubidaRespuesta(resultados=resultados, total_movimientos=total)


@router.get("")
async def mis_archivos(usuario: UsuarioAutenticado = Depends(usuario_activo)) -> list[dict]:
    """Historial de archivos procesados del usuario."""
    return listar_archivos(usuario.id)


@router.delete("/{archivo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def borrar_archivo(
    archivo_id: str, usuario: UsuarioAutenticado = Depends(usuario_activo)
) -> None:
    """Borra un archivo y todos sus movimientos (por si se cargó uno equivocado)."""
    eliminar_archivo(usuario.id, archivo_id)
