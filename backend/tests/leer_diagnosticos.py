"""Lee los diagnósticos enviados desde /diagnostico.

Temporal, igual que la tabla: cuando el problema del selector en celular esté
cerrado, se borra junto con el endpoint.

Uso:  python tests/leer_diagnosticos.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_client  # noqa: E402


def main() -> int:
    filas = (
        get_client()
        .table("diagnosticos")
        .select("*")
        .order("creado_at", desc=True)
        .limit(10)
        .execute()
        .data
        or []
    )

    if not filas:
        print("No hay diagnósticos guardados todavía.")
        return 0

    for fila in filas:
        agente = fila.get("agente") or ""
        if agente.startswith(("verificacion", "prueba local")):
            continue  # los míos, no interesan

        print("=" * 78)
        print(f"Fecha:    {fila['creado_at']}")
        print(f"Pantalla: {fila.get('pantalla')}   táctil={fila.get('tactil')}")
        print(f"Agente:   {agente}")

        registro = fila.get("registro") or []
        print(f"\nEventos registrados: {len(registro)}")
        if not registro:
            print("  (VACÍO — el evento change nunca se disparó)")
        for evento in registro:
            print(f"\n  [{evento.get('t')}] {evento.get('evento')}")
            if "cantidad" in evento:
                print(f"      archivos recibidos: {evento['cantidad']}")
            for archivo in evento.get("archivos") or []:
                print(
                    f"        nombre={archivo.get('nombre')!r}  "
                    f"tamaño={archivo.get('tamano')}  tipo={archivo.get('tipo')!r}"
                )
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
