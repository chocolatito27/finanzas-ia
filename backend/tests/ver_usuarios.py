"""Lista las cuentas y su estado de activación. Útil para operar el producto.

Uso:  python tests/ver_usuarios.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings  # noqa: E402
from database import get_client  # noqa: E402


def main() -> int:
    cliente = get_client()

    usuarios = cliente.auth.admin.list_users()
    perfiles = {
        p["id"]: p
        for p in (cliente.table("perfiles").select("*").execute().data or [])
    }

    print(f"{'EMAIL':<42}{'CONFIRMADO':<12}{'ACTIVO':<9}{'ONBOARDING':<12}NEGOCIO")
    print("-" * 100)
    for u in usuarios:
        perfil = perfiles.get(u.id, {})
        print(
            f"{(u.email or '?'):<42}"
            f"{('sí' if u.email_confirmed_at else 'NO'):<12}"
            f"{('sí' if perfil.get('activo') else 'no'):<9}"
            f"{('sí' if perfil.get('onboarding_completo') else 'no'):<12}"
            f"{perfil.get('nombre_negocio') or '-'}"
        )

    print()
    print(f"Total de cuentas: {len(usuarios)}")
    print(f"Emails con acceso al panel /admin: {', '.join(sorted(settings.admin_emails))}")

    sin_cuenta = [
        e for e in settings.admin_emails
        if not any((u.email or "").lower() == e for u in usuarios)
    ]
    if sin_cuenta:
        print()
        print("AVISO: estos emails están configurados como admin pero NO tienen cuenta,")
        print("       así que no pueden iniciar sesión ni entrar a /admin:")
        for e in sin_cuenta:
            print(f"       - {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
