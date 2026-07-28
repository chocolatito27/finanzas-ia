"""Aplica sql/schema.sql al proyecto Supabase usando la Management API.

Uso:
    python sql/apply_schema.py            # aplica schema.sql
    python sql/apply_schema.py otro.sql   # aplica otro archivo

Requiere la variable de entorno SUPABASE_ACCESS_TOKEN (el token sbp_...)
y SUPABASE_PROJECT_REF.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
PROJECT_REF = os.environ.get("SUPABASE_PROJECT_REF", "")


def run_sql(sql: str) -> object:
    body = json.dumps({"query": sql}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            # Sin un User-Agent normal, Cloudflare bloquea la petición (error 1010)
            "User-Agent": "finanzas-ia-setup/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8") or "[]")


def main() -> int:
    if not TOKEN or not PROJECT_REF:
        print("Falta SUPABASE_ACCESS_TOKEN o SUPABASE_PROJECT_REF", file=sys.stderr)
        return 2

    archivo = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("schema.sql")
    # utf-8-sig descarta el BOM que agregan los editores de Windows
    sql = archivo.read_text(encoding="utf-8-sig")

    try:
        resultado = run_sql(sql)
    except urllib.error.HTTPError as exc:
        print(f"ERROR {exc.code}: {exc.read().decode('utf-8', 'replace')}", file=sys.stderr)
        return 1

    print(f"OK — {archivo.name} aplicado")
    print(json.dumps(resultado, indent=2, ensure_ascii=False)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
