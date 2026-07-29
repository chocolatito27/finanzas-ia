"""Utilidades compartidas por las pruebas automatizadas.

**Por qué existe este módulo.** Las pruebas corren contra la base de datos real.
Al principio usaban la misma cuenta que una persona podía estar usando para
explorar la app, y empezaban borrando *todos* sus archivos para ser repetibles.
Eso destruyó datos reales una vez. Dos reglas para que no vuelva a pasar:

  1. Las pruebas usan su **propia cuenta** (`qa-automatizado@...`), separada de la
     cuenta de exploración `prueba@finanzasia.test`.
  2. Solo borran archivos que ellas mismas subieron, reconocibles porque el nombre
     empieza con `ejemplo_`. Nunca borran a ciegas.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings  # noqa: E402
from database import get_client  # noqa: E402

API = "http://127.0.0.1:8000"

# Cuenta exclusiva de las pruebas automatizadas. NO la uses para explorar la app:
# lo que subas aquí se borra sin aviso en la siguiente corrida.
EMAIL = "qa-automatizado@finanzasia.test"
PASSWORD = "qa-automatizado-123456"

SAMPLES = Path(__file__).parent / "samples"
PREFIJO_EJEMPLOS = "ejemplo_"


def asegurar_usuario() -> str:
    """Crea (si falta) la cuenta de pruebas, confirmada y con suscripción activa."""
    cliente = get_client()
    existente = next(
        (u for u in cliente.auth.admin.list_users() if u.email == EMAIL), None
    )
    if existente:
        user_id = existente.id
    else:
        creado = cliente.auth.admin.create_user(
            {"email": EMAIL, "password": PASSWORD, "email_confirm": True}
        )
        user_id = creado.user.id

    cliente.table("perfiles").upsert(
        {
            "id": user_id,
            "email": EMAIL,
            "nombre_negocio": "QA Automatizado",
            "activo": True,
            "onboarding_completo": True,
        },
        on_conflict="id",
    ).execute()
    return user_id


def token() -> str:
    respuesta = httpx.post(
        f"{settings.supabase_url}/auth/v1/token?grant_type=password",
        headers={"apikey": settings.supabase_anon_key},
        json={"email": EMAIL, "password": PASSWORD},
        timeout=30,
    )
    respuesta.raise_for_status()
    return respuesta.json()["access_token"]


def cliente_api() -> httpx.Client:
    asegurar_usuario()
    return httpx.Client(
        base_url=API, headers={"Authorization": f"Bearer {token()}"}, timeout=300
    )


def limpiar_ejemplos(cliente: httpx.Client) -> int:
    """Borra solo los archivos de ejemplo que subieron las pruebas.

    Cualquier otro archivo se deja intacto: si alguien subió algo real a esta
    cuenta, no es la prueba quien debe decidir borrarlo.
    """
    borrados = 0
    for archivo in cliente.get("/api/archivos").json():
        if (archivo.get("nombre_archivo") or "").startswith(PREFIJO_EJEMPLOS):
            cliente.delete(f"/api/archivos/{archivo['id']}")
            borrados += 1
    return borrados


def limpiar_todo(cliente: httpx.Client) -> int:
    """Borra TODOS los archivos, pero solo si la sesión es la cuenta de QA.

    `limpiar_ejemplos` filtra por nombre y no alcanza cuando una prueba sube el
    mismo contenido con nombres arbitrarios (el caso de los nombres que entregan
    los celulares): el archivo queda, y su hash hace que la subida siguiente se
    rechace como duplicada.

    La comprobación del email no es decorativa: es lo que impide que este borrado
    se ejecute contra una cuenta real si alguien reutiliza la función.
    """
    perfil = cliente.get("/api/auth/perfil").json()
    if (perfil.get("email") or "").lower() != EMAIL:
        raise RuntimeError(
            f"limpiar_todo solo opera sobre {EMAIL}, no sobre {perfil.get('email')}"
        )

    borrados = 0
    for archivo in cliente.get("/api/archivos").json():
        cliente.delete(f"/api/archivos/{archivo['id']}")
        borrados += 1
    return borrados


def subir(cliente: httpx.Client, *nombres: str) -> list[dict]:
    """Sube archivos de tests/samples/ y devuelve los resultados."""
    archivos = []
    for nombre in nombres:
        ruta = SAMPLES / nombre
        if not ruta.exists():
            raise FileNotFoundError(
                f"Falta {ruta.name}. Corre primero: python tests/generar_ejemplos.py"
            )
        archivos.append(("archivos", (ruta.name, ruta.read_bytes(), "application/pdf")))
    respuesta = cliente.post("/api/archivos/subir", files=archivos)
    respuesta.raise_for_status()
    return respuesta.json()["resultados"]
