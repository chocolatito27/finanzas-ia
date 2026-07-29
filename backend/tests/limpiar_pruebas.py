"""Borra las cuentas de prueba, dejando intactas las reales.

Solo toca cuentas cuyo email termina en `@finanzasia.test`, que es el dominio
reservado para pruebas. Cualquier cuenta de un correo real se queda.

Uso:  python tests/limpiar_pruebas.py            (muestra qué borraría)
      python tests/limpiar_pruebas.py --borrar    (borra de verdad)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_client  # noqa: E402

DOMINIO_PRUEBAS = "@finanzasia.test"
# Estas dos se conservan: una para explorar la app a mano, la otra la usan las
# pruebas automatizadas. Borrarlas obliga a recrearlas.
CONSERVAR = {"prueba@finanzasia.test", "qa-automatizado@finanzasia.test"}


def main() -> int:
    borrar_de_verdad = "--borrar" in sys.argv
    cliente = get_client()

    candidatas = [
        u for u in cliente.auth.admin.list_users()
        if (u.email or "").lower().endswith(DOMINIO_PRUEBAS)
        and (u.email or "").lower() not in CONSERVAR
    ]

    if not candidatas:
        print("No hay cuentas de prueba sobrantes.")
        return 0

    print(f"Cuentas de prueba sobrantes ({len(candidatas)}):")
    for u in candidatas:
        print(f"  {u.email}")

    if not borrar_de_verdad:
        print("\nEsto fue solo una vista previa.")
        print("Para borrarlas: python tests/limpiar_pruebas.py --borrar")
        return 0

    for u in candidatas:
        cliente.auth.admin.delete_user(u.id)
        print(f"  borrada  {u.email}")
    print(f"\n{len(candidatas)} cuenta(s) borradas. Sus movimientos se fueron en cascada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
