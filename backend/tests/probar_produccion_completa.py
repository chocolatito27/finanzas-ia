"""Recorre en PRODUCCIÓN todos los caminos de la subida, no solo el feliz.

Existe porque las pruebas anteriores solo cubrían producción con un PDF sin
contraseña, y el caso real de un usuario —un estado de cuenta del BCP protegido—
nunca se ejecutó contra el servidor desplegado.

Uso:  python tests/probar_produccion_completa.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _comun import EMAIL, PASSWORD, SAMPLES, asegurar_usuario  # noqa: E402
from config import settings  # noqa: E402

API = "https://finanzas-ia-api.onrender.com"
CLAVE_CORRECTA = "12345678"


def sesion() -> httpx.Client:
    token = httpx.post(
        f"{settings.supabase_url}/auth/v1/token?grant_type=password",
        headers={"apikey": settings.supabase_anon_key},
        json={"email": EMAIL, "password": PASSWORD},
        timeout=60,
    ).json()["access_token"]
    return httpx.Client(
        base_url=API, headers={"Authorization": f"Bearer {token}"}, timeout=300
    )


def limpiar(cliente: httpx.Client) -> None:
    for archivo in cliente.get("/api/archivos").json():
        cliente.delete(f"/api/archivos/{archivo['id']}")


def subir(cliente: httpx.Client, nombre: str, contenido: bytes) -> dict:
    limpiar(cliente)
    respuesta = cliente.post(
        "/api/archivos/subir",
        files=[("archivos", (nombre, contenido, "application/pdf"))],
    )
    respuesta.raise_for_status()
    return respuesta.json()["resultados"][0]


def main() -> int:
    fallos = 0
    asegurar_usuario()
    protegido = (SAMPLES / "ejemplo_bcp_clave.pdf").read_bytes()

    print(f"Probando {API}\n")

    with sesion() as cliente:
        # --- 1. PDF protegido SIN clave guardada ---
        print("1) PDF con contraseña y SIN clave guardada")
        cliente.post("/api/auth/clave-pdf", json={"clave_pdf": "clave-que-no-sirve"})
        res = subir(cliente, "ejemplo_bcp_clave.pdf", protegido)
        print(f"   ok={res['ok']}  codigo={res.get('codigo_error')}")
        print(f"   mensaje: {res.get('error')}")
        if res["ok"] or res.get("codigo_error") != "PDF_PROTEGIDO":
            print("   FALLO: debía rechazarlo con PDF_PROTEGIDO y un mensaje claro")
            fallos += 1

        # --- 2. Guardar la clave correcta y reintentar ---
        print("\n2) Guardar la clave correcta y volver a subir el MISMO archivo")
        r = cliente.post("/api/auth/clave-pdf", json={"clave_pdf": CLAVE_CORRECTA})
        print(f"   clave guardada: HTTP {r.status_code}  "
              f"tiene_clave={r.json().get('tiene_clave_pdf')}")

        res = subir(cliente, "ejemplo_bcp_clave.pdf", protegido)
        print(f"   ok={res['ok']}  banco={res.get('banco_detectado')}  "
              f"movimientos={res.get('movimientos_insertados')}")
        if not res["ok"]:
            print(f"   FALLO: {res.get('codigo_error')} — {res.get('error')}")
            fallos += 1
        elif res["movimientos_insertados"] != 12:
            print(f"   FALLO: esperaba 12 movimientos, llegaron "
                  f"{res['movimientos_insertados']}")
            fallos += 1

        # --- 3. El dashboard refleja lo procesado ---
        print("\n3) El dashboard ve los movimientos")
        dash = cliente.get("/api/movimientos/dashboard").json()
        print(f"   total={dash['total_movimientos']}  "
              f"meses={len(dash['resumen_mensual'])}")
        if dash["total_movimientos"] != 12:
            print("   FALLO: el dashboard no cuadra con lo subido")
            fallos += 1

        # --- 4. Un PDF que no es estado de cuenta ---
        print("\n4) Un PDF válido pero sin movimientos")
        pdf_vacio = (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\ntrailer<</Root 1 0 R>>"
        )
        res = subir(cliente, "cualquiera.pdf", pdf_vacio)
        print(f"   ok={res['ok']}  codigo={res.get('codigo_error')}")
        print(f"   mensaje: {res.get('error')}")
        if res["ok"]:
            print("   FALLO: no debería aceptar un PDF sin movimientos")
            fallos += 1

        limpiar(cliente)

    print(f"\n{'=' * 68}")
    print("Todos los caminos OK en producción" if fallos == 0
          else f"{fallos} fallo(s) en producción")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
