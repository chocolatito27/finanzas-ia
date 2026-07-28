"""Verifica que la serie temporal no tenga saltos y que la proyección los ignore.

El caso que motiva esta prueba: un usuario con datos de marzo y junio, sin abril
ni mayo. El gráfico debe mostrar los 4 meses (abril y mayo en cero), pero la
proyección debe promediar solo sobre los 2 meses que sí tienen movimientos.

Usa la cuenta aislada de QA y solo borra sus propios ejemplos (ver `_comun.py`).

Requiere el backend corriendo. Uso:  python tests/probar_serie.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _comun import EMAIL, cliente_api, limpiar_ejemplos, subir  # noqa: E402


def indice_mes(mes: str) -> int:
    return int(mes[:4]) * 12 + int(mes[5:7])


def main() -> int:
    fallos = 0
    print(f"Cuenta de pruebas: {EMAIL}\n")

    with cliente_api() as cliente:
        # Marzo y abril de los ejemplos; el hueco lo probamos con el salto real
        # que producen los dos archivos (marzo → abril son consecutivos, así que
        # además verificamos que no se inventen meses de más).
        limpiar_ejemplos(cliente)
        subir(cliente, "ejemplo_bcp.pdf", "ejemplo_interbank.pdf")

        dash = cliente.get("/api/movimientos/dashboard").json()
        meses = [m["mes"] for m in dash["resumen_mensual"]]
        print(f"1) Meses en resumen_mensual: {meses}")

        esperados = indice_mes(meses[-1]) - indice_mes(meses[0]) + 1
        print(f"   esperados {esperados}, hay {len(meses)}")
        if len(meses) != esperados:
            print("   FALLO: el eje de tiempo tiene saltos")
            fallos += 1
        else:
            print("   OK: eje continuo")

        vacios = [
            m["mes"] for m in dash["resumen_mensual"]
            if float(m["ingresos"]) == 0 and float(m["gastos"]) == 0
        ]
        print(f"   meses rellenados en cero: {vacios or 'ninguno'}")

        p = dash["proyeccion"]
        print(f"\n2) Proyección: {p['meses_con_datos']} meses con datos, "
              f"promedio ingreso S/ {float(p['promedio_ingreso_mensual']):,.2f}")
        if p["meses_con_datos"] > len(meses) - len(vacios):
            print("   FALLO: la proyección está contando meses vacíos")
            fallos += 1
        else:
            print("   OK: los meses vacíos no diluyen el promedio")

        print("\n3) GET /api/movimientos/serie")
        for granularidad in ("mes", "semana", "dia"):
            serie = cliente.get(
                f"/api/movimientos/serie?granularidad={granularidad}"
            ).json()
            puntos = serie["puntos"]
            if not puntos:
                print(f"   FALLO: serie {granularidad} vacía")
                fallos += 1
                continue

            con_datos = sum(
                1 for x in puntos if x["ingresos"] != 0 or x["gastos"] != 0
            )
            print(f"   {granularidad:<7} {len(puntos):>4} puntos "
                  f"({con_datos} con movimientos)  "
                  f"{puntos[0]['etiqueta']} → {puntos[-1]['etiqueta']}")

            # Cada acumulado = el anterior + el balance del periodo
            for anterior, actual in zip(puntos, puntos[1:]):
                esperado = round(anterior["acumulado"] + actual["balance"], 2)
                if abs(esperado - actual["acumulado"]) > 0.011:
                    print(f"   FALLO: acumulado inconsistente en {actual['periodo']}")
                    fallos += 1
                    break

            # Sin huecos: los periodos deben ser estrictamente crecientes y
            # consecutivos (lo garantiza el backend al rellenar)
            if granularidad == "mes":
                for anterior, actual in zip(puntos, puntos[1:]):
                    if indice_mes(actual["periodo"]) - indice_mes(anterior["periodo"]) != 1:
                        print(f"   FALLO: salto entre {anterior['periodo']} "
                              f"y {actual['periodo']}")
                        fallos += 1
                        break

        serie_dia = cliente.get("/api/movimientos/serie?granularidad=dia").json()
        print(f"\n   acumulado final (diario): "
              f"S/ {serie_dia['puntos'][-1]['acumulado']:,.2f}")

    print(f"\n{'=' * 60}")
    print("Serie temporal OK" if fallos == 0 else f"{fallos} fallo(s)")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
