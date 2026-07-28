"""Perfil del usuario y onboarding.

El registro y el login los hace el frontend directamente contra Supabase Auth
(no se reimplementa autenticación aquí). Este router solo maneja el perfil de
negocio que acompaña a la cuenta.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from database import actualizar_perfil, crear_perfil_si_falta
from models import ClavePdfIn, OnboardingIn, PerfilOut
from security import UsuarioAutenticado, cifrar_clave, usuario_actual

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _a_perfil_out(perfil: dict, usuario: UsuarioAutenticado) -> PerfilOut:
    return PerfilOut(
        id=perfil["id"],
        email=perfil.get("email") or usuario.email,
        nombre_negocio=perfil.get("nombre_negocio"),
        activo=bool(perfil.get("activo")),
        onboarding_completo=bool(perfil.get("onboarding_completo")),
        tiene_clave_pdf=bool(perfil.get("clave_pdf")),
        es_admin=usuario.es_admin,
        created_at=perfil.get("created_at"),
    )


@router.get("/perfil", response_model=PerfilOut)
async def mi_perfil(usuario: UsuarioAutenticado = Depends(usuario_actual)) -> PerfilOut:
    """Perfil del usuario logueado. Lo crea si por algún motivo no existía."""
    perfil = crear_perfil_si_falta(usuario.id, usuario.email)
    return _a_perfil_out(perfil, usuario)


@router.post("/onboarding", response_model=PerfilOut)
async def guardar_onboarding(
    datos: OnboardingIn, usuario: UsuarioAutenticado = Depends(usuario_actual)
) -> PerfilOut:
    """Guarda el nombre del negocio y, cifrada, la clave de los PDFs bancarios."""
    crear_perfil_si_falta(usuario.id, usuario.email)

    campos: dict = {
        "nombre_negocio": datos.nombre_negocio.strip(),
        "onboarding_completo": True,
        "email": usuario.email,
    }
    # Si el usuario deja la clave vacía, se conserva la que ya tenía.
    if datos.clave_pdf:
        campos["clave_pdf"] = cifrar_clave(datos.clave_pdf.strip())

    perfil = actualizar_perfil(usuario.id, campos)
    return _a_perfil_out(perfil or {"id": usuario.id}, usuario)


@router.post("/clave-pdf", response_model=PerfilOut)
async def actualizar_clave_pdf(
    datos: ClavePdfIn, usuario: UsuarioAutenticado = Depends(usuario_actual)
) -> PerfilOut:
    """Actualiza solo la clave de los PDFs (cuando la anterior dejó de funcionar).

    No pide el nombre del negocio: el usuario que llega aquí ya pasó el onboarding
    y solo quiere corregir la clave.
    """
    clave = datos.clave_pdf.strip()
    if not clave:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La clave no puede estar vacía")

    crear_perfil_si_falta(usuario.id, usuario.email)
    perfil = actualizar_perfil(usuario.id, {"clave_pdf": cifrar_clave(clave)})
    return _a_perfil_out(perfil or {"id": usuario.id}, usuario)
