"""Reproduce el caso del celular: archivos cuyo nombre no trae extensión.

Los selectores de archivos móviles (Google Drive, Archivos, adjuntos de WhatsApp)
suelen entregar el archivo con un nombre sin extensión o con un nombre genérico.
Si el backend decide el formato solo por el nombre, rechaza PDFs perfectamente
válidos.

Uso:  python tests/probar_nombres_moviles.py   (requiere el backend corriendo)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _comun import SAMPLES, cliente_api, limpiar_todo  # noqa: E402

# Nombres tal como los entregan los selectores móviles
CASOS = [
    ("ejemplo_bcp.pdf", "nombre normal"),
    ("ejemplo_bcp", "sin extensión (Google Drive en Android)"),
    ("ejemplo_bcp.PDF", "extensión en mayúsculas"),
    ("Documento", "nombre genérico sin extensión"),
    ("estado de cuenta marzo.pdf", "con espacios"),
]


def main() -> int:
    contenido = (SAMPLES / "ejemplo_bcp.pdf").read_bytes()
    fallos = 0

    with cliente_api() as cliente:
        for nombre, descripcion in CASOS:
            # Todos los casos suben el MISMO contenido con distinto nombre, así que
            # hay que dejar la cuenta vacía entre uno y otro: si no, el control de
            # duplicados por hash rechaza el segundo y en adelante.
            limpiar_todo(cliente)

            respuesta = cliente.post(
                "/api/archivos/subir",
                files=[("archivos", (nombre, contenido, "application/pdf"))],
            )
            res = respuesta.json()["resultados"][0]
            estado = "OK " if res["ok"] else "ERR"
            detalle = (
                f"{res['movimientos_insertados']} movimientos"
                if res["ok"]
                else f"{res.get('codigo_error')}: {res.get('error')}"
            )
            print(f"  [{estado}] {descripcion:<42} '{nombre}'")
            print(f"         {detalle}")
            if not res["ok"]:
                fallos += 1

        # No dejar residuos: el hash de estos archivos bloquearía otras pruebas
        limpiar_todo(cliente)

    print(f"\n{'=' * 70}")
    if fallos:
        print(f"{fallos} de {len(CASOS)} nombres fueron rechazados aunque el "
              f"contenido era un PDF válido")
    else:
        print("Todos los nombres aceptados: el formato se decide por el contenido")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
