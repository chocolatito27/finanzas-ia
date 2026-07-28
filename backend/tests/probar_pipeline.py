"""Prueba el pipeline completo: PDF → extracción → categorización con Venice/Claude.

Hace una llamada real a la API de Venice. Uso:  python tests/probar_pipeline.py
"""

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings  # noqa: E402
from models import CATEGORIAS_GASTO, CATEGORIAS_INGRESO, Categoria  # noqa: E402
from services.ia_categorizer import categorizar_movimientos  # noqa: E402
from services.pdf_extractor import extraer_movimientos_pdf  # noqa: E402

SAMPLES = Path(__file__).parent / "samples"


async def main() -> int:
    faltantes = settings.validar()
    if faltantes:
        print(f"Faltan variables en .env: {', '.join(faltantes)}")
        return 1

    ruta = SAMPLES / "ejemplo_bcp.pdf"
    if not ruta.exists():
        print("Corre primero: python tests/generar_ejemplos.py")
        return 1

    print(f"Modelo: {settings.venice_model}  @  {settings.venice_base_url}\n")

    extraccion = extraer_movimientos_pdf(ruta.read_bytes())
    print(f"1) Extracción: {len(extraccion.movimientos)} movimientos "
          f"del banco {extraccion.banco}\n")

    print("2) Categorizando con la IA...")
    categorizados = await categorizar_movimientos(extraccion.movimientos)

    print(f"\n{'=' * 92}")
    print(f"{'FECHA':<12}{'MONTO':>12}  {'CATEGORÍA':<24}{'DESCRIPCIÓN LIMPIA'}")
    print("=" * 92)
    for m in categorizados:
        print(f"{m.fecha!s:<12}{m.monto:>12,.2f}  {m.categoria.value:<24}{m.descripcion_limpia}")

    # --- Totales como los calculará el dashboard ---
    ingresos = sum(
        (m.monto for m in categorizados if m.categoria in CATEGORIAS_INGRESO), Decimal(0)
    )
    gastos = sum(
        (abs(m.monto) for m in categorizados if m.categoria in CATEGORIAS_GASTO), Decimal(0)
    )
    internas = [m for m in categorizados if m.categoria == Categoria.TRANSFERENCIA_INTERNA]
    desconocidos = [m for m in categorizados if m.categoria == Categoria.DESCONOCIDO]

    por_categoria: dict[str, list] = defaultdict(list)
    for m in categorizados:
        por_categoria[m.categoria.value].append(m)

    print(f"\n{'-' * 92}")
    for categoria, items in sorted(por_categoria.items()):
        total = sum((abs(i.monto) for i in items), Decimal(0))
        print(f"  {categoria:<24} {len(items):>2} mov.   S/ {total:>10,.2f}")
    print(f"{'-' * 92}")
    print(f"  INGRESOS (sin transferencias internas): S/ {ingresos:,.2f}")
    print(f"  GASTOS   (sin transferencias internas): S/ {gastos:,.2f}")
    print(f"  BALANCE:                                S/ {ingresos - gastos:,.2f}")
    print(f"  Transferencias internas excluidas: {len(internas)}")
    print(f"  Sin clasificar (DESCONOCIDO): {len(desconocidos)}")

    # --- Chequeos de sanidad ---
    problemas = []
    if len(categorizados) != len(extraccion.movimientos):
        problemas.append("se perdieron movimientos entre extracción y categorización")
    for m in categorizados:
        if m.monto > 0 and m.categoria in CATEGORIAS_GASTO:
            problemas.append(f"ingreso clasificado como gasto: {m.descripcion_original}")
        if m.monto < 0 and m.categoria in CATEGORIAS_INGRESO:
            problemas.append(f"gasto clasificado como ingreso: {m.descripcion_original}")
    if len(desconocidos) > len(categorizados) / 2:
        problemas.append("más de la mitad quedó como DESCONOCIDO: revisar el prompt")

    print()
    if problemas:
        for p in problemas:
            print(f"  PROBLEMA: {p}")
        return 1
    print("  Pipeline OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
