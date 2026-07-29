"""Verifica el backend YA DESPLEGADO, no el local.

Comprueba lo que un usuario real haría desde el celular: subir un PDF cuyo nombre
no trae extensión, tal como lo entregan los selectores de archivos móviles.

Uso:  python tests/probar_produccion.py
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


def main() -> int:
    fallos = 0
    asegurar_usuario()

    print(f"Probando {API}")
    print("(si el servicio estaba dormido, la primera llamada tarda ~1 minuto)\n")

    salud = httpx.get(f"{API}/api/salud", timeout=180).json()
    print(f"1) Salud: ok={salud['ok']}  modelo={salud['modelo_ia']}")
    if not salud["ok"]:
        print(f"   FALLO: faltan variables {salud['variables_faltantes']}")
        fallos += 1

    token = httpx.post(
        f"{settings.supabase_url}/auth/v1/token?grant_type=password",
        headers={"apikey": settings.supabase_anon_key},
        json={"email": EMAIL, "password": PASSWORD},
        timeout=60,
    ).json()["access_token"]

    with httpx.Client(
        base_url=API, headers={"Authorization": f"Bearer {token}"}, timeout=300
    ) as cliente:
        for archivo in cliente.get("/api/archivos").json():
            cliente.delete(f"/api/archivos/{archivo['id']}")

        contenido = (SAMPLES / "ejemplo_bcp.pdf").read_bytes()

        print("\n2) Subida con nombre SIN extensión (el caso del celular)")
        res = cliente.post(
            "/api/archivos/subir",
            files=[("archivos", ("Documento", contenido, "application/octet-stream"))],
        ).json()["resultados"][0]
        print(f"   ok={res['ok']}  banco={res['banco_detectado']}  "
              f"movimientos={res['movimientos_insertados']}")
        if not res["ok"]:
            print(f"   FALLO: {res.get('codigo_error')} — {res.get('error')}")
            fallos += 1

        print("\n3) Una imagen debe rechazarse con un mensaje entendible")
        jpg = b"\xff\xd8\xff\xe0" + b"\x00" * 200
        res = cliente.post(
            "/api/archivos/subir",
            files=[("archivos", ("foto.jpg", jpg, "image/jpeg"))],
        ).json()["resultados"][0]
        print(f"   ok={res['ok']}  codigo={res.get('codigo_error')}")
        print(f"   mensaje: {res.get('error')}")
        if res["ok"]:
            print("   FALLO: aceptó una imagen")
            fallos += 1

        print("\n4) El dashboard ve lo que se subió")
        dash = cliente.get("/api/movimientos/dashboard").json()
        print(f"   movimientos={dash['total_movimientos']}  "
              f"meses={len(dash['resumen_mensual'])}")
        if dash["total_movimientos"] == 0:
            print("   FALLO: el dashboard está vacío")
            fallos += 1

        for archivo in cliente.get("/api/archivos").json():
            cliente.delete(f"/api/archivos/{archivo['id']}")

    print(f"\n{'=' * 60}")
    print("Producción OK" if fallos == 0 else f"{fallos} fallo(s) en producción")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
