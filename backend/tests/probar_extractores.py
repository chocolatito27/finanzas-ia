"""Prueba los extractores contra los archivos de tests/samples/ y muestra el resultado.

Uso:  python tests/probar_extractores.py
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.excel_extractor import extraer_movimientos_excel  # noqa: E402
from services.pdf_extractor import (  # noqa: E402
    ErrorExtraccion,
    extraer_movimientos_pdf,
)

SAMPLES = Path(__file__).parent / "samples"


def mostrar(titulo: str, resultado) -> None:
    print(f"\n{'=' * 78}")
    print(f"{titulo}  |  banco: {resultado.banco or 'no detectado'}  |  "
          f"{len(resultado.movimientos)} movimientos  "
          f"({resultado.mes_inicio} → {resultado.mes_fin})")
    print("=" * 78)
    ingresos = sum((m["monto"] for m in resultado.movimientos if m["monto"] > 0), Decimal(0))
    gastos = sum((m["monto"] for m in resultado.movimientos if m["monto"] < 0), Decimal(0))
    for m in resultado.movimientos:
        signo = "+" if m["monto"] > 0 else " "
        print(f"  {m['fecha']}  {signo}{m['monto']:>11,.2f}   {m['descripcion'][:52]}")
    print(f"  {'-' * 74}")
    print(f"  INGRESOS: S/ {ingresos:,.2f}    GASTOS: S/ {abs(gastos):,.2f}    "
          f"BALANCE: S/ {ingresos + gastos:,.2f}")


def main() -> int:
    if not SAMPLES.exists():
        print("Faltan los ejemplos. Corre primero: python tests/generar_ejemplos.py")
        return 1

    fallos = 0

    # --- PDF con columnas cargo/abono ---
    try:
        r = extraer_movimientos_pdf((SAMPLES / "ejemplo_bcp.pdf").read_bytes())
        mostrar("BCP (cargo/abono/saldo)", r)
        assert len(r.movimientos) == 12, f"esperaba 12, salieron {len(r.movimientos)}"
        assert r.banco == "BCP"
        assert r.movimientos[0]["monto"] == Decimal("4850.00")
        assert r.movimientos[1]["monto"] == Decimal("-2310.50")
    except Exception as exc:
        print(f"FALLO BCP: {exc}")
        fallos += 1

    # --- PDF con una sola columna de monto ---
    try:
        r = extraer_movimientos_pdf((SAMPLES / "ejemplo_interbank.pdf").read_bytes())
        mostrar("Interbank (monto único + saldo)", r)
        assert len(r.movimientos) == 6, f"esperaba 6, salieron {len(r.movimientos)}"
        assert r.banco == "INTERBANK"
        assert r.movimientos[0]["monto"] == Decimal("5200.00"), "el abono debe ser positivo"
        assert r.movimientos[1]["monto"] == Decimal("-3100.00"), "el pago debe ser negativo"
    except Exception as exc:
        print(f"FALLO Interbank: {exc}")
        fallos += 1

    # --- PDF protegido: sin clave debe fallar con código claro ---
    protegido = (SAMPLES / "ejemplo_bcp_clave.pdf").read_bytes()
    try:
        extraer_movimientos_pdf(protegido)
        print("FALLO: el PDF protegido se abrió sin clave")
        fallos += 1
    except ErrorExtraccion as exc:
        print(f"\nPDF protegido sin clave → {exc.codigo}: OK")

    # --- PDF protegido con la clave correcta ---
    try:
        r = extraer_movimientos_pdf(protegido, clave="12345678")
        mostrar("BCP protegido (clave correcta)", r)
        assert len(r.movimientos) == 12
    except Exception as exc:
        print(f"FALLO PDF protegido con clave: {exc}")
        fallos += 1

    # --- PDF protegido con clave incorrecta ---
    try:
        extraer_movimientos_pdf(protegido, clave="00000000")
        print("FALLO: se abrió con clave incorrecta")
        fallos += 1
    except ErrorExtraccion as exc:
        print(f"PDF protegido con clave errada → {exc.codigo}: OK")

    # --- Excel ---
    try:
        r = extraer_movimientos_excel((SAMPLES / "ejemplo_bbva.xlsx").read_bytes(), "ejemplo_bbva.xlsx")
        mostrar("BBVA (Excel)", r)
        assert len(r.movimientos) == 6, f"esperaba 6, salieron {len(r.movimientos)}"
        assert r.movimientos[0]["monto"] == Decimal("7300.00")
        assert r.movimientos[1]["monto"] == Decimal("-4100.00")
    except Exception as exc:
        print(f"FALLO Excel: {exc}")
        fallos += 1

    print(f"\n{'=' * 78}")
    print("TODO OK" if fallos == 0 else f"{fallos} prueba(s) fallaron")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
