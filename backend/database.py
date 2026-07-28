"""Cliente de Supabase y helpers de acceso a datos.

El backend usa la *service_role key*, que hace bypass de RLS. Por eso **cada consulta
filtra explícitamente por `user_id`**: la seguridad la garantiza el código, no la
base de datos. Nunca aceptar un `user_id` que venga del cliente.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from supabase import Client, create_client

from config import settings

logger = logging.getLogger(__name__)

_cliente: Client | None = None


def get_client() -> Client:
    """Devuelve el cliente de Supabase con permisos de servicio (singleton)."""
    global _cliente
    if _cliente is None:
        if not settings.supabase_url or not settings.supabase_service_key:
            raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY no configuradas")
        _cliente = create_client(settings.supabase_url, settings.supabase_service_key)
    return _cliente


# ------------------------------------------------------------------ perfiles


def obtener_perfil(user_id: str) -> dict[str, Any] | None:
    respuesta = (
        get_client().table("perfiles").select("*").eq("id", user_id).limit(1).execute()
    )
    return respuesta.data[0] if respuesta.data else None


def crear_perfil_si_falta(user_id: str, email: str | None) -> dict[str, Any]:
    """El trigger de Postgres ya lo crea al registrarse; esto cubre el caso raro."""
    perfil = obtener_perfil(user_id)
    if perfil:
        return perfil
    get_client().table("perfiles").upsert(
        {"id": user_id, "email": email}, on_conflict="id"
    ).execute()
    return obtener_perfil(user_id) or {"id": user_id, "email": email, "activo": False}


def actualizar_perfil(user_id: str, campos: dict[str, Any]) -> dict[str, Any] | None:
    if not campos:
        return obtener_perfil(user_id)
    get_client().table("perfiles").update(campos).eq("id", user_id).execute()
    return obtener_perfil(user_id)


def listar_perfiles() -> list[dict[str, Any]]:
    respuesta = (
        get_client()
        .table("perfiles")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return respuesta.data or []


# ------------------------------------------------------------------ archivos


def buscar_archivo_por_hash(user_id: str, hash_archivo: str) -> dict[str, Any] | None:
    respuesta = (
        get_client()
        .table("archivos_procesados")
        .select("*")
        .eq("user_id", user_id)
        .eq("hash_archivo", hash_archivo)
        .limit(1)
        .execute()
    )
    return respuesta.data[0] if respuesta.data else None


def registrar_archivo(
    user_id: str,
    nombre_archivo: str,
    hash_archivo: str,
    banco: str | None,
    mes_inicio: date | None,
    mes_fin: date | None,
    total_movimientos: int,
) -> dict[str, Any]:
    respuesta = (
        get_client()
        .table("archivos_procesados")
        .insert(
            {
                "user_id": user_id,
                "nombre_archivo": nombre_archivo,
                "hash_archivo": hash_archivo,
                "banco_detectado": banco,
                "mes_inicio": mes_inicio.isoformat() if mes_inicio else None,
                "mes_fin": mes_fin.isoformat() if mes_fin else None,
                "total_movimientos": total_movimientos,
                "estado": "procesado",
            }
        )
        .execute()
    )
    return respuesta.data[0]


def eliminar_archivo(user_id: str, archivo_id: str) -> None:
    """Borra el archivo y, por ON DELETE CASCADE, sus movimientos."""
    (
        get_client()
        .table("archivos_procesados")
        .delete()
        .eq("id", archivo_id)
        .eq("user_id", user_id)
        .execute()
    )


def listar_archivos(user_id: str) -> list[dict[str, Any]]:
    respuesta = (
        get_client()
        .table("archivos_procesados")
        .select("*")
        .eq("user_id", user_id)
        .order("procesado_at", desc=True)
        .execute()
    )
    return respuesta.data or []


# ------------------------------------------------------------------ movimientos


LOTE_INSERCION = 500


def insertar_movimientos(
    user_id: str, archivo_id: str, movimientos: list[Any]
) -> int:
    """Inserta los movimientos categorizados. Devuelve cuántos se insertaron."""
    if not movimientos:
        return 0

    filas = [
        {
            "user_id": user_id,
            "archivo_id": archivo_id,
            "fecha": m.fecha.isoformat(),
            "monto": str(m.monto),
            "descripcion_original": m.descripcion_original[:500],
            "descripcion_limpia": m.descripcion_limpia[:500],
            "categoria": m.categoria.value,
        }
        for m in movimientos
    ]

    insertados = 0
    cliente = get_client()
    for i in range(0, len(filas), LOTE_INSERCION):
        lote = filas[i : i + LOTE_INSERCION]
        respuesta = cliente.table("movimientos").insert(lote).execute()
        insertados += len(respuesta.data or [])
    return insertados


def listar_movimientos(
    user_id: str,
    categoria: str | None = None,
    mes: str | None = None,
    limite: int | None = None,
) -> list[dict[str, Any]]:
    """Movimientos del usuario, opcionalmente filtrados por categoría y mes (YYYY-MM)."""
    consulta = (
        get_client()
        .table("movimientos")
        .select("id, fecha, monto, descripcion_original, descripcion_limpia, categoria")
        .eq("user_id", user_id)
    )
    if categoria:
        consulta = consulta.eq("categoria", categoria)
    if mes:
        anio, numero_mes = int(mes[:4]), int(mes[5:7])
        inicio = date(anio, numero_mes, 1)
        fin = date(anio + (numero_mes == 12), (numero_mes % 12) + 1, 1)
        consulta = consulta.gte("fecha", inicio.isoformat()).lt("fecha", fin.isoformat())

    consulta = consulta.order("fecha", desc=True)
    if limite:
        consulta = consulta.limit(limite)
    return consulta.execute().data or []


def todos_los_movimientos(user_id: str) -> list[dict[str, Any]]:
    """Trae todos los movimientos del usuario paginando (Supabase corta en 1000)."""
    filas: list[dict[str, Any]] = []
    pagina, tamanio = 0, 1000
    cliente = get_client()
    while True:
        respuesta = (
            cliente.table("movimientos")
            .select("id, fecha, monto, categoria")
            .eq("user_id", user_id)
            .order("fecha")
            .range(pagina * tamanio, (pagina + 1) * tamanio - 1)
            .execute()
        )
        lote = respuesta.data or []
        filas.extend(lote)
        if len(lote) < tamanio:
            return filas
        pagina += 1


def actualizar_categoria(user_id: str, movimiento_id: str, categoria: str) -> bool:
    respuesta = (
        get_client()
        .table("movimientos")
        .update({"categoria": categoria})
        .eq("id", movimiento_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(respuesta.data)


def contar_movimientos_por_usuario() -> dict[str, int]:
    """Para el panel de admin: cuántos movimientos tiene cada usuario."""
    conteo: dict[str, int] = {}
    pagina, tamanio = 0, 1000
    cliente = get_client()
    while True:
        respuesta = (
            cliente.table("movimientos")
            .select("user_id")
            .range(pagina * tamanio, (pagina + 1) * tamanio - 1)
            .execute()
        )
        lote = respuesta.data or []
        for fila in lote:
            conteo[fila["user_id"]] = conteo.get(fila["user_id"], 0) + 1
        if len(lote) < tamanio:
            return conteo
        pagina += 1


def a_decimal(valor: Any) -> Decimal:
    """Supabase devuelve DECIMAL como string; esto lo normaliza."""
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor or "0"))
