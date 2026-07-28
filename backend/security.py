"""Autenticación y cifrado.

**Autenticación.** El frontend inicia sesión con Supabase Auth y manda el access
token en `Authorization: Bearer ...`. Aquí se valida contra el endpoint
`/auth/v1/user` de Supabase, que es el único modo que funciona tanto con los JWT
simétricos (legacy) como con las nuevas claves asimétricas, sin tener que
sincronizar secretos. Las validaciones se cachean 60 s para no llamar a Supabase
en cada request.

**Cifrado.** La clave de los PDFs del usuario (su DNI) se guarda cifrada con Fernet.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings

logger = logging.getLogger(__name__)

TTL_CACHE_SEGUNDOS = 60
esquema_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class UsuarioAutenticado:
    id: str
    email: str

    @property
    def es_admin(self) -> bool:
        return self.email.lower() in settings.admin_emails


# ------------------------------------------------------------------ cache


_cache: dict[str, tuple[float, UsuarioAutenticado]] = {}


def _clave_cache(token: str) -> str:
    # Se guarda el hash, no el token, para no tener credenciales en memoria en claro.
    return hashlib.sha256(token.encode()).hexdigest()


def _cache_get(token: str) -> UsuarioAutenticado | None:
    entrada = _cache.get(_clave_cache(token))
    if entrada is None:
        return None
    expira, usuario = entrada
    if time.monotonic() > expira:
        _cache.pop(_clave_cache(token), None)
        return None
    return usuario


def _cache_set(token: str, usuario: UsuarioAutenticado) -> None:
    if len(_cache) > 1000:  # tope simple para que no crezca sin control
        _cache.clear()
    _cache[_clave_cache(token)] = (time.monotonic() + TTL_CACHE_SEGUNDOS, usuario)


# ------------------------------------------------------------------ validación


async def _validar_token(token: str) -> UsuarioAutenticado:
    en_cache = _cache_get(token)
    if en_cache:
        return en_cache

    try:
        async with httpx.AsyncClient(timeout=10.0) as cliente:
            respuesta = await cliente.get(
                f"{settings.supabase_url}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": settings.supabase_anon_key,
                },
            )
    except httpx.HTTPError as exc:
        logger.error("No se pudo contactar a Supabase Auth: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No se pudo verificar la sesión. Intenta de nuevo.",
        ) from exc

    if respuesta.status_code != 200:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida o expirada")

    datos = respuesta.json()
    if not datos.get("id"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida")

    usuario = UsuarioAutenticado(id=datos["id"], email=datos.get("email") or "")
    _cache_set(token, usuario)
    return usuario


async def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
) -> UsuarioAutenticado:
    """Dependencia de FastAPI: exige un usuario logueado."""
    if credenciales is None or not credenciales.credentials:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Falta el token de sesión",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _validar_token(credenciales.credentials)


async def usuario_activo(
    usuario: UsuarioAutenticado = Depends(usuario_actual),
) -> UsuarioAutenticado:
    """Exige además que la suscripción esté activa (o que sea admin)."""
    from database import crear_perfil_si_falta

    if usuario.es_admin:
        return usuario

    perfil = crear_perfil_si_falta(usuario.id, usuario.email)
    if not perfil.get("activo"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Tu suscripción todavía no está activa. "
            "Escríbenos por WhatsApp para activarla.",
        )
    return usuario


async def usuario_admin(
    usuario: UsuarioAutenticado = Depends(usuario_actual),
) -> UsuarioAutenticado:
    """Exige que el email esté en ADMIN_EMAILS."""
    if not usuario.es_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No tienes acceso a esta sección")
    return usuario


# ------------------------------------------------------------------ cifrado


def _fernet() -> Fernet:
    if not settings.clave_encryption_key:
        raise RuntimeError("CLAVE_ENCRYPTION_KEY no configurada")
    return Fernet(settings.clave_encryption_key.encode())


def cifrar_clave(texto: str) -> str:
    return _fernet().encrypt(texto.encode()).decode()


def descifrar_clave(cifrado: str | None) -> str | None:
    """Devuelve None si no hay clave guardada o si no se puede descifrar."""
    if not cifrado:
        return None
    try:
        return _fernet().decrypt(cifrado.encode()).decode()
    except (InvalidToken, ValueError):
        logger.warning("No se pudo descifrar la clave_pdf (¿cambió CLAVE_ENCRYPTION_KEY?)")
        return None
