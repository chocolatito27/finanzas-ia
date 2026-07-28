"""Panel de administración (solo para los emails de ADMIN_EMAILS).

Sirve para lo único que necesita el MVP: ver quién se registró y marcar la cuenta
como activa cuando la persona pagó por Yape/Plin.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from database import (
    actualizar_perfil,
    contar_movimientos_por_usuario,
    listar_perfiles,
    obtener_perfil,
)
from models import CambiarEstadoIn, UsuarioAdmin
from security import UsuarioAutenticado, usuario_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/usuarios", response_model=list[UsuarioAdmin])
async def listar_usuarios(
    admin: UsuarioAutenticado = Depends(usuario_admin),
) -> list[UsuarioAdmin]:
    """Todos los usuarios registrados, con cuántos movimientos tiene cada uno."""
    conteo = contar_movimientos_por_usuario()
    return [
        UsuarioAdmin(
            id=p["id"],
            email=p.get("email"),
            nombre_negocio=p.get("nombre_negocio"),
            activo=bool(p.get("activo")),
            onboarding_completo=bool(p.get("onboarding_completo")),
            total_movimientos=conteo.get(p["id"], 0),
            created_at=p.get("created_at"),
        )
        for p in listar_perfiles()
    ]


@router.patch("/usuarios/{user_id}/estado", response_model=UsuarioAdmin)
async def cambiar_estado(
    user_id: str,
    datos: CambiarEstadoIn,
    admin: UsuarioAutenticado = Depends(usuario_admin),
) -> UsuarioAdmin:
    """Activa o desactiva la suscripción de un usuario."""
    if not obtener_perfil(user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")

    perfil = actualizar_perfil(user_id, {"activo": datos.activo})
    logger.info(
        "Admin %s marcó a %s como %s",
        admin.email, user_id, "ACTIVO" if datos.activo else "INACTIVO",
    )
    conteo = contar_movimientos_por_usuario()
    return UsuarioAdmin(
        id=perfil["id"],
        email=perfil.get("email"),
        nombre_negocio=perfil.get("nombre_negocio"),
        activo=bool(perfil.get("activo")),
        onboarding_completo=bool(perfil.get("onboarding_completo")),
        total_movimientos=conteo.get(perfil["id"], 0),
        created_at=perfil.get("created_at"),
    )
