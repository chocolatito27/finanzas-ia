"""Genera estados de cuenta de ejemplo para probar los extractores sin datos reales.

Crea en tests/samples/:
  - ejemplo_bcp.pdf        : formato CARGO / ABONO / SALDO (columnas separadas)
  - ejemplo_interbank.pdf  : formato MONTO / SALDO (una sola columna de importe)
  - ejemplo_bcp_clave.pdf  : el mismo BCP pero protegido con la clave "12345678"
  - ejemplo_bbva.xlsx      : export de Excel con bloque de titular arriba

Uso:  python tests/generar_ejemplos.py
"""

from __future__ import annotations

import io
from pathlib import Path

import pikepdf
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

SAMPLES = Path(__file__).parent / "samples"

# (fecha, descripción, cargo, abono)  — cargo=gasto, abono=ingreso
MOVIMIENTOS_BCP = [
    ("03/03/2026", "TRANSF RECIBIDA HENRIS SAC", None, 4850.00),
    ("05/03/2026", "PAGO PROVEEDOR AROMAS PERU SAC", 2310.50, None),
    ("07/03/2026", "YAPE RECIBIDO MARIA QUISPE", None, 180.00),
    ("09/03/2026", "ALQUILER LOCAL GAMARRA MARZO", 1200.00, None),
    ("11/03/2026", "COMPRA POS SODIMAC SURQUILLO", 345.90, None),
    ("14/03/2026", "TRANSF RECIBIDA DISTRIB LIMA EIRL", None, 6720.00),
    ("15/03/2026", "ITF IMPUESTO A LAS TRANSACCIONES", 3.15, None),
    ("18/03/2026", "PAGO RECIBO LUZ DEL SUR", 289.40, None),
    ("20/03/2026", "RETIRO CAJERO AGENCIA MIRAFLORES", 800.00, None),
    ("22/03/2026", "TRANSFERENCIA A CUENTA PROPIA AHORROS", 1500.00, None),
    ("25/03/2026", "TRANSF RECIBIDA PERFUMES ELITE SAC", None, 3980.00),
    ("28/03/2026", "PAGO INTERNET CLARO EMPRESAS", 149.00, None),
]

MOVIMIENTOS_INTERBANK = [
    ("02/04/2026", "ABONO TRANSFERENCIA INTERBANCARIA", 5200.00),
    ("06/04/2026", "PAGO A PROVEEDOR ESENCIAS DEL NORTE", 3100.00),
    ("10/04/2026", "COMPRA VISA MERCADO MAYORISTA", 780.25),
    ("15/04/2026", "DEPOSITO EN EFECTIVO AGENCIA", 2400.00),
    ("21/04/2026", "RETIRO PERSONAL SOCIO", 1000.00),
    ("27/04/2026", "PAGO SERVICIO AGUA SEDAPAL", 95.60),
]


def _fmt(valor: float | None) -> str:
    return f"{valor:,.2f}" if valor is not None else ""


def generar_pdf_bcp(ruta: Path) -> None:
    """Formato con columnas CARGO / ABONO / SALDO separadas."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    ancho, alto = A4
    y = alto - 60

    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, y, "BANCO DE CREDITO DEL PERU - BCP")
    y -= 18
    c.setFont("Helvetica", 9)
    c.drawString(50, y, "ESTADO DE CUENTA CORRIENTE - MONEDA: SOLES (S/)")
    y -= 13
    c.drawString(50, y, "TITULAR: IMPORTACIONES TOMAS SAC     CUENTA: 194-2345678-0-11")
    y -= 13
    c.drawString(50, y, "PERIODO: 01/03/2026 AL 31/03/2026")
    y -= 28

    # Encabezado de la tabla — las X definen las columnas
    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, y, "FECHA")
    c.drawString(105, y, "DESCRIPCION")
    c.drawRightString(400, y, "CARGO")
    c.drawRightString(470, y, "ABONO")
    c.drawRightString(545, y, "SALDO")
    y -= 6
    c.line(50, y, 545, y)
    y -= 14

    c.setFont("Helvetica", 8)
    saldo = 12000.00
    c.drawString(105, y, "SALDO ANTERIOR")
    c.drawRightString(545, y, _fmt(saldo))
    y -= 13

    for fecha, descripcion, cargo, abono in MOVIMIENTOS_BCP:
        saldo = saldo - (cargo or 0) + (abono or 0)
        c.drawString(50, y, fecha)
        c.drawString(105, y, descripcion)
        c.drawRightString(400, y, _fmt(cargo))
        c.drawRightString(470, y, _fmt(abono))
        c.drawRightString(545, y, _fmt(saldo))
        y -= 13

    y -= 8
    c.setFont("Helvetica-Bold", 8)
    c.drawString(105, y, "SALDO FINAL")
    c.drawRightString(545, y, _fmt(saldo))

    c.showPage()
    c.save()
    ruta.write_bytes(buffer.getvalue())
    print(f"  {ruta.name}")


def generar_pdf_interbank(ruta: Path) -> None:
    """Formato con una sola columna MONTO: el signo se deduce del texto o del saldo."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    ancho, alto = A4
    y = alto - 60

    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, y, "INTERBANK")
    y -= 18
    c.setFont("Helvetica", 9)
    c.drawString(50, y, "ESTADO DE CUENTA - CUENTA NEGOCIOS SOLES")
    y -= 13
    c.drawString(50, y, "PERIODO: 01/04/2026 - 30/04/2026")
    y -= 28

    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, y, "FECHA")
    c.drawString(115, y, "OPERACION")
    c.drawRightString(450, y, "MONTO")
    c.drawRightString(545, y, "SALDO")
    y -= 6
    c.line(50, y, 545, y)
    y -= 14

    c.setFont("Helvetica", 8)
    saldo = 8000.00
    for fecha, descripcion, monto in MOVIMIENTOS_INTERBANK:
        es_ingreso = descripcion.startswith(("ABONO", "DEPOSITO"))
        saldo = saldo + monto if es_ingreso else saldo - monto
        c.drawString(50, y, fecha)
        c.drawString(115, y, descripcion)
        c.drawRightString(450, y, _fmt(monto))
        c.drawRightString(545, y, _fmt(saldo))
        y -= 13

    c.showPage()
    c.save()
    ruta.write_bytes(buffer.getvalue())
    print(f"  {ruta.name}")


def proteger_pdf(origen: Path, destino: Path, clave: str) -> None:
    with pikepdf.open(origen) as pdf:
        pdf.save(destino, encryption=pikepdf.Encryption(user=clave, owner=clave))
    print(f"  {destino.name} (clave: {clave})")


def generar_excel_bbva(ruta: Path) -> None:
    """Export típico: bloque de datos del titular arriba y luego la tabla."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Movimientos"

    hoja.append(["BBVA CONTINENTAL"])
    hoja.append(["Estado de cuenta"])
    hoja.append(["Titular:", "IMPORTACIONES TOMAS SAC"])
    hoja.append(["Cuenta:", "0011-0234-0100123456"])
    hoja.append(["Periodo:", "01/05/2026 - 31/05/2026"])
    hoja.append([])
    hoja.append(["Fecha", "Concepto", "Cargo", "Abono", "Saldo"])

    filas = [
        ("2026-05-04", "TRANSFERENCIA RECIBIDA CLIENTE VIP", None, 7300.00),
        ("2026-05-08", "PAGO PROVEEDOR FRAGANCIAS SAC", 4100.00, None),
        ("2026-05-12", "COMISION MANTENIMIENTO CUENTA", 15.00, None),
        ("2026-05-16", "ABONO VENTA ONLINE MERCADO PAGO", None, 2150.75),
        ("2026-05-22", "PAGO ALQUILER OFICINA", 1800.00, None),
        ("2026-05-29", "RETIRO PERSONAL GERENCIA", 2000.00, None),
    ]
    saldo = 5000.00
    for fecha, concepto, cargo, abono in filas:
        saldo = saldo - (cargo or 0) + (abono or 0)
        hoja.append([fecha, concepto, cargo, abono, round(saldo, 2)])

    libro.save(ruta)
    print(f"  {ruta.name}")


def main() -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    print("Generando ejemplos en tests/samples/:")
    bcp = SAMPLES / "ejemplo_bcp.pdf"
    generar_pdf_bcp(bcp)
    generar_pdf_interbank(SAMPLES / "ejemplo_interbank.pdf")
    proteger_pdf(bcp, SAMPLES / "ejemplo_bcp_clave.pdf", "12345678")
    generar_excel_bbva(SAMPLES / "ejemplo_bbva.xlsx")


if __name__ == "__main__":
    main()
