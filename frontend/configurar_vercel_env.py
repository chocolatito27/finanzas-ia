"""Configura las variables de entorno del proyecto en Vercel usando su API REST.

**Por qué no se usa `vercel env add`.** Pasarle el valor por una tubería de
PowerShell le antepone un BOM (U+FEFF) invisible. Ese carácter terminó pegado al
inicio de la clave de Supabase, y el navegador rechazó la petición entera con
"String contains non ISO-8859-1 code point" porque un header HTTP no admite
caracteres fuera de Latin-1. Mandar el JSON directo a la API evita cualquier
traducción de la shell.

Uso:
    set VERCEL_TOKEN=...
    python configurar_vercel_env.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

TOKEN = os.environ.get("VERCEL_TOKEN", "")
PROYECTO = os.environ.get("VERCEL_PROJECT", "finanzas-ia")
ENTORNOS = ["production", "preview", "development"]

VARIABLES = {
    "VITE_SUPABASE_URL": "https://yfbronqatbidcktjygor.supabase.co",
    "VITE_SUPABASE_ANON_KEY": (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlmYnJvbnFhdGJpZGNrdGp5Z29yIiwicm9sZSI6"
        "ImFub24iLCJpYXQiOjE3ODUyNDUxOTEsImV4cCI6MjEwMDgyMTE5MX0."
        "4SvgHVBXGjgCAK20dH5YA-zQYvLF6bmYysZU7CDAAFI"
    ),
    "VITE_API_URL": "https://finanzas-ia-api.onrender.com",
    # Respaldo: el valor que manda es el WHATSAPP_NUMBER del backend, que se lee
    # en tiempo de ejecución. Este solo se usa si la API no responde.
    "VITE_WHATSAPP_NUMBER": "6285640549937",
    "VITE_ADMIN_EMAILS": "gustavo.araujot@unmsm.edu.pe,tomasaraujotejada2007@gmail.com",
}


def pedir(metodo: str, ruta: str, cuerpo: dict | None = None):
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    req = urllib.request.Request(
        f"https://api.vercel.com{ruta}",
        data=datos,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "finanzas-ia-setup/1.0",
        },
        method=metodo,
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        texto = resp.read().decode("utf-8")
        return json.loads(texto) if texto else {}


def main() -> int:
    if not TOKEN:
        print("Falta VERCEL_TOKEN", file=sys.stderr)
        return 2

    # Se borran las anteriores: si una quedó con basura invisible, sobrescribirla
    # no siempre la limpia. Partir de cero es más barato que depurarlo.
    existentes = pedir("GET", f"/v10/projects/{PROYECTO}/env?decrypt=true").get("envs", [])
    for env in existentes:
        if env["key"] in VARIABLES:
            pedir("DELETE", f"/v9/projects/{PROYECTO}/env/{env['id']}")
            print(f"  borrada  {env['key']}")

    for clave, valor in VARIABLES.items():
        if any(ord(c) > 126 for c in valor):
            print(f"  ABORTADO: {clave} tiene caracteres no ASCII", file=sys.stderr)
            return 1
        # type="plain" y no "encrypted": todas estas variables terminan dentro del
        # JavaScript que se descarga en el navegador, así que no son secretas. En
        # claro se pueden releer y verificar que no traigan basura invisible; en
        # "encrypted" la API devuelve el blob cifrado y no hay forma de comprobarlo.
        pedir(
            "POST",
            f"/v10/projects/{PROYECTO}/env",
            {"key": clave, "value": valor, "type": "plain", "target": ENTORNOS},
        )
        print(f"  creada   {clave}  ({len(valor)} caracteres)")

    # Verificación: se relee lo guardado y se compara carácter a carácter
    print("\nVerificando lo que quedó guardado:")
    guardadas = pedir("GET", f"/v10/projects/{PROYECTO}/env?decrypt=true").get("envs", [])
    fallos = 0
    for env in guardadas:
        esperado = VARIABLES.get(env["key"])
        if esperado is None:
            continue
        real = env.get("value") or ""
        if real == esperado:
            print(f"  OK   {env['key']}")
        else:
            raros = [f"U+{ord(c):04X}" for c in real if ord(c) > 126]
            print(f"  MAL  {env['key']}: len={len(real)} esperado={len(esperado)} "
                  f"{'caracteres raros: ' + ','.join(raros) if raros else ''}")
            fallos += 1

    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
