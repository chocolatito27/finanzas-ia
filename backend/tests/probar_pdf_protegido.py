"""Verifica el flujo de PDFs con contraseña de punta a punta.

Comprueba que la clave guardada por el usuario (cifrada en la base) sirve para
abrir un PDF protegido, y que una clave equivocada da un error claro.

Usa la cuenta aislada de QA y solo borra sus propios ejemplos (ver `_comun.py`).

Requiere el backend corriendo. Uso:  python tests/probar_pdf_protegido.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _comun import EMAIL, cliente_api, limpiar_ejemplos, subir  # noqa: E402

CLAVE_PDF = "12345678"
PROTEGIDO = "ejemplo_bcp_clave.pdf"


def main() -> int:
    fallos = 0
    print(f"Cuenta de pruebas: {EMAIL}\n")

    with cliente_api() as cliente:
        # --- 1. Guardar la clave correcta ---
        print("1) POST /api/auth/clave-pdf con la clave correcta")
        r = cliente.post("/api/auth/clave-pdf", json={"clave_pdf": CLAVE_PDF})
        print(f"   status={r.status_code}  "
              f"tiene_clave_pdf={r.json().get('tiene_clave_pdf')}")
        if r.status_code != 200:
            print(f"   FALLO: {r.text[:300]}")
            fallos += 1

        # --- 2. Subir el PDF protegido: debe abrirse ---
        print("\n2) Subir el PDF protegido con esa clave")
        limpiar_ejemplos(cliente)
        res = subir(cliente, PROTEGIDO)[0]
        print(f"   ok={res['ok']}  banco={res['banco_detectado']}  "
              f"movimientos={res['movimientos_insertados']}")
        if not res["ok"]:
            print(f"   FALLO: {res.get('error')}")
            fallos += 1
        elif res["movimientos_insertados"] != 12:
            print(f"   FALLO: esperaba 12, llegaron {res['movimientos_insertados']}")
            fallos += 1

        # --- 3. Clave equivocada: error claro, no genérico ---
        print("\n3) Guardar una clave equivocada y reintentar")
        cliente.post("/api/auth/clave-pdf", json={"clave_pdf": "00000000"})
        limpiar_ejemplos(cliente)
        res = subir(cliente, PROTEGIDO)[0]
        print(f"   ok={res['ok']}  codigo={res.get('codigo_error')}")
        print(f"   mensaje: {res.get('error')}")
        if res["ok"] or res.get("codigo_error") != "PDF_PROTEGIDO":
            print("   FALLO: debía rechazarlo con codigo_error=PDF_PROTEGIDO")
            fallos += 1

        # --- 4. Body sin la clave: 422 nombrando el campo ---
        print("\n4) POST /api/auth/clave-pdf sin la clave")
        r = cliente.post("/api/auth/clave-pdf", json={})
        detalle = r.json().get("detail")
        campo = detalle[0]["loc"][-1] if isinstance(detalle, list) else None
        print(f"   status={r.status_code}  campo reportado={campo}")
        if r.status_code != 422 or campo != "clave_pdf":
            print("   FALLO: debía reportar que falta clave_pdf")
            fallos += 1

        # Dejar la cuenta con la clave correcta
        cliente.post("/api/auth/clave-pdf", json={"clave_pdf": CLAVE_PDF})

    print(f"\n{'=' * 60}")
    print("PDFs con clave OK" if fallos == 0 else f"{fallos} fallo(s)")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
