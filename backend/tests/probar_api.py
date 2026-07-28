"""Prueba end-to-end de la API: login, subida, dashboard, filtros y corrección.

Corre contra la cuenta aislada `qa-automatizado@finanzasia.test` y solo borra los
archivos que ella misma sube (ver `_comun.py`). No toca datos de nadie más.

Requiere el backend corriendo. Uso:  python tests/probar_api.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _comun import EMAIL, cliente_api, limpiar_ejemplos, subir  # noqa: E402


def main() -> int:
    fallos = 0
    print(f"Cuenta de pruebas: {EMAIL}\n")

    with cliente_api() as cliente:
        # --- perfil ---
        print("1) GET /api/auth/perfil")
        perfil = cliente.get("/api/auth/perfil").json()
        print(f"   negocio={perfil['nombre_negocio']}  activo={perfil['activo']}")
        if not perfil["activo"]:
            print("   FALLO: el usuario debería estar activo")
            fallos += 1

        borrados = limpiar_ejemplos(cliente)
        print(f"   ejemplos de corridas anteriores borrados: {borrados}")

        # --- subida ---
        print("\n2) POST /api/archivos/subir (2 archivos, tarda ~30-60 s)")
        resultados = subir(cliente, "ejemplo_bcp.pdf", "ejemplo_interbank.pdf")
        total = 0
        for r in resultados:
            estado = "OK " if r["ok"] else "ERR"
            detalle = (
                f"{r['movimientos_insertados']} movimientos · {r['banco_detectado']}"
                if r["ok"]
                else r["error"]
            )
            print(f"   [{estado}] {r['nombre_archivo']}: {detalle}")
            total += r["movimientos_insertados"]
        print(f"   total insertado: {total}")
        if total != 18:
            print(f"   FALLO: esperaba 18 movimientos, llegaron {total}")
            fallos += 1

        # --- duplicado ---
        print("\n3) Reintento del mismo archivo (debe rechazarse por duplicado)")
        codigo = subir(cliente, "ejemplo_bcp.pdf")[0].get("codigo_error")
        print(f"   codigo_error={codigo}")
        if codigo != "DUPLICADO":
            print("   FALLO: no se detectó el duplicado")
            fallos += 1

        # --- dashboard ---
        print("\n4) GET /api/movimientos/dashboard")
        dash = cliente.get("/api/movimientos/dashboard").json()
        mes = dash["mes_actual"]
        print(f"   mes actual: {mes['mes']}")
        print(f"     ingresos S/ {float(mes['ingresos']):>10,.2f}")
        print(f"     gastos   S/ {float(mes['gastos']):>10,.2f}")
        print(f"     balance  S/ {float(mes['balance']):>10,.2f}")
        print(f"   meses en el eje: {len(dash['resumen_mensual'])}")
        print(f"   total movimientos: {dash['total_movimientos']}")
        print(f"   sin clasificar: {dash['movimientos_desconocidos']}")

        print("\n   por categoría:")
        for c in dash["por_categoria"]:
            print(f"     {c['categoria']:<24} {c['cantidad']:>2}   "
                  f"S/ {float(c['total']):>10,.2f}")

        p = dash["proyeccion"]
        print(f"\n   proyección {p['anio']} (confiable={p['confiable']}, "
              f"{p['meses_con_datos']} meses con datos):")
        print(f"     ingresos al cierre S/ {float(p['ingresos_proyectados_cierre']):>12,.2f}")
        print(f"     gastos al cierre   S/ {float(p['gastos_proyectados_cierre']):>12,.2f}")
        print(f"     balance al cierre  S/ {float(p['balance_proyectado_cierre']):>12,.2f}")

        if dash["total_movimientos"] != 18:
            print("   FALLO: el dashboard no ve los 18 movimientos")
            fallos += 1
        if len(dash["resumen_mensual"]) != 2:
            print("   FALLO: esperaba marzo y abril en el eje")
            fallos += 1

        internas = next(
            (c for c in dash["por_categoria"]
             if c["categoria"] == "TRANSFERENCIA_INTERNA"),
            None,
        )
        if internas:
            en_meses = sum(
                float(m["ingresos"]) + float(m["gastos"])
                for m in dash["resumen_mensual"]
            )
            en_categorias = sum(float(c["total"]) for c in dash["por_categoria"])
            if abs(en_categorias - en_meses - float(internas["total"])) > 1:
                print("   AVISO: revisar la exclusión de transferencias internas")
            else:
                print(f"\n   Transferencias internas excluidas correctamente "
                      f"(S/ {float(internas['total']):,.2f} fuera del cálculo)")

        # --- filtros ---
        print("\n5) GET /api/movimientos con filtros")
        marzo = cliente.get("/api/movimientos?mes=2026-03").json()
        proveedores = cliente.get("/api/movimientos?categoria=GASTO_PROVEEDOR").json()
        print(f"   marzo 2026: {len(marzo)} movimientos")
        print(f"   GASTO_PROVEEDOR: {len(proveedores)} movimientos")
        if len(marzo) != 12:
            print(f"   FALLO: marzo debería tener 12, tiene {len(marzo)}")
            fallos += 1

        # --- corrección de categoría ---
        print("\n6) PATCH categoría de un movimiento")
        objetivo = marzo[0]
        original = objetivo["categoria"]
        candidatas = (
            ["GASTO_OPERATIVO", "GASTO_PERSONAL", "GASTO_PROVEEDOR"]
            if float(objetivo["monto"]) < 0
            else ["INGRESO_VENTA", "INGRESO_TRANSFERENCIA"]
        )
        nueva = next(c for c in candidatas if c != original)
        cliente.patch(
            f"/api/movimientos/{objetivo['id']}/categoria", json={"categoria": nueva}
        )
        verificado = cliente.get("/api/movimientos?mes=2026-03").json()
        actual = next(m for m in verificado if m["id"] == objetivo["id"])["categoria"]
        print(f"   {original} → {actual}")
        if actual != nueva:
            print("   FALLO: la categoría no cambió")
            fallos += 1
        cliente.patch(
            f"/api/movimientos/{objetivo['id']}/categoria", json={"categoria": original}
        )

    print(f"\n{'=' * 60}")
    print("API OK — flujo completo verificado" if fallos == 0 else f"{fallos} fallo(s)")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
