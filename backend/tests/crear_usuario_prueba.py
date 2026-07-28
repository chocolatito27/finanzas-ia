"""Crea (o reutiliza) un usuario de prueba ya confirmado y activo.

Sirve para recorrer el flujo completo en local sin depender del correo de
confirmación de Supabase.

Uso:  python tests/crear_usuario_prueba.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings  # noqa: E402
from database import get_client  # noqa: E402

EMAIL = "prueba@finanzasia.test"
PASSWORD = "prueba123456"


def main() -> int:
    cliente = get_client()

    usuarios = cliente.auth.admin.list_users()
    existente = next((u for u in usuarios if u.email == EMAIL), None)

    if existente:
        user_id = existente.id
        print(f"Usuario ya existía: {EMAIL} ({user_id})")
    else:
        creado = cliente.auth.admin.create_user(
            {"email": EMAIL, "password": PASSWORD, "email_confirm": True}
        )
        user_id = creado.user.id
        print(f"Usuario creado: {EMAIL} ({user_id})")

    # El trigger de Postgres ya creó el perfil; aquí se activa y se completa
    # el onboarding para poder entrar directo al dashboard.
    cliente.table("perfiles").upsert(
        {
            "id": user_id,
            "email": EMAIL,
            "nombre_negocio": "Importaciones Tomás SAC",
            "activo": True,
            "onboarding_completo": True,
        },
        on_conflict="id",
    ).execute()

    print(f"Perfil activo y con onboarding completo.")
    print()
    print("  Entra en http://localhost:5173/login con:")
    print(f"    email:      {EMAIL}")
    print(f"    contraseña: {PASSWORD}")
    print()
    print(f"  Admin configurado: {', '.join(settings.admin_emails) or '(ninguno)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
