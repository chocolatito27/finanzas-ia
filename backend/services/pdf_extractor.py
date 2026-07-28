"""Extracción de movimientos desde PDFs de estados de cuenta bancarios peruanos.

Cada banco (BCP, Interbank, BBVA, Scotiabank, ...) maquetea su PDF distinto, así que
el extractor no asume un formato rígido. Trabaja en tres niveles, del más preciso al
más tolerante:

  1. **Por posición de columnas** — lee las palabras con sus coordenadas X, encuentra
     la fila de encabezados ("FECHA / DESCRIPCIÓN / CARGO / ABONO / SALDO") y asigna
     cada importe a su columna según dónde cae en la página. Es el más confiable
     porque el signo sale de la columna, no de adivinar.

  2. **Por saldo corrido** — si el estado trae columna de saldo, se corrige el signo
     de cada movimiento comparando el saldo con el de la línea anterior. Esto arregla
     los casos donde el encabezado no se detectó bien.

  3. **Por palabras clave** — último recurso: se deduce el signo del texto
     ("PAGO", "RETIRO" → gasto; "ABONO", "DEPÓSITO" → ingreso).
"""

from __future__ import annotations

import io
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

import pdfplumber
import pikepdf

logger = logging.getLogger(__name__)


# ============================================================ errores


class ErrorExtraccion(Exception):
    """Error de extracción con un código que el frontend puede interpretar."""

    codigo = "ERROR_EXTRACCION"

    def __init__(self, mensaje: str, codigo: str | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        if codigo:
            self.codigo = codigo


class PdfProtegidoError(ErrorExtraccion):
    codigo = "PDF_PROTEGIDO"


class NoReconocidoError(ErrorExtraccion):
    codigo = "NO_RECONOCIDO"


# ============================================================ constantes


BANCOS: dict[str, tuple[str, ...]] = {
    "BCP": ("banco de credito", "viabcp", "bcp", "credito del peru"),
    "INTERBANK": ("interbank", "banco internacional del peru"),
    "BBVA": ("bbva", "continental"),
    "SCOTIABANK": ("scotiabank", "scotia"),
    "MIBANCO": ("mibanco",),
    "BANBIF": ("banbif", "interamericano de finanzas"),
    "PICHINCHA": ("pichincha",),
    "FALABELLA": ("falabella",),
    "YAPE": ("yape",),
}

MESES_ES: dict[str, int] = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}

# Encabezados de columna, normalizados sin tildes
CABECERAS = {
    "fecha": ("fecha", "fec", "dia", "fechaoper", "fechaproceso", "fechavalor"),
    "descripcion": (
        "descripcion", "descripciones", "operacion", "operaciones", "concepto",
        "detalle", "referencia", "movimiento", "glosa", "transaccion",
    ),
    "cargo": ("cargo", "cargos", "debe", "debito", "retiro", "retiros", "egreso",
              "egresos", "salida", "salidas", "debitos"),
    "abono": ("abono", "abonos", "haber", "credito", "deposito", "depositos",
              "ingreso", "ingresos", "entrada", "entradas", "creditos"),
    "monto": ("monto", "montos", "importe", "importes", "valor"),
    "saldo": ("saldo", "saldos", "balance", "saldocontable", "saldodisponible"),
}

# Palabras que delatan un gasto o un ingreso cuando no hay columnas claras
PISTAS_GASTO = (
    "pago", "retiro", "compra", "cargo", "debito", "itf", "comision", "comisiones",
    "mantenimiento", "portes", "envio", "consumo", "pos ", "transferencia a ",
    "transf a ", "giro", "cuota", "amortizacion", "seguro", "impuesto", "penalidad",
    "yape enviado", "plin enviado", "recarga",
)
PISTAS_INGRESO = (
    "abono", "deposito", "transferencia de", "transf de", "transf recibida",
    "recibida", "recibido", "interes", "intereses", "devolucion", "reembolso",
    "extorno", "anulacion", "yape recibido", "plin recibido", "haber", "ingreso",
    "venta", "cobro",
)

# Líneas que no son movimientos aunque tengan fecha y monto
RUIDO = (
    "saldo anterior", "saldo inicial", "saldo final", "saldo disponible",
    "saldo contable", "total cargos", "total abonos", "totales", "subtotal",
    "estado de cuenta", "pagina", "página", "resumen", "tasa de interes",
    "linea de credito", "numero de cuenta", "titular", "moneda",
)

# Importe con 2 decimales obligatorios: descarta números de operación y DNIs.
RE_MONTO = re.compile(
    r"^[\(\-]?\s*(?:s/\.?|us\$|\$|pen)?\s*"      # símbolo de moneda opcional
    r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+[.,]\d{2})"
    r"\s*[\)\-]?$",
    re.IGNORECASE,
)
RE_FECHA_NUM = re.compile(r"^(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?$")
# Los exports a Excel/CSV suelen traer la fecha en ISO (2026-05-04)
RE_FECHA_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ].*)?$")
RE_FECHA_MES = re.compile(
    r"^(\d{1,2})[\s\-/]*(" + "|".join(MESES_ES) + r")[\s\-/]*(\d{2,4})?$", re.IGNORECASE
)
RE_ANIO = re.compile(r"\b(20\d{2})\b")


# ============================================================ utilidades


def _normalizar(texto: str) -> str:
    """minúsculas, sin tildes — para comparar encabezados y palabras clave."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return sin_tildes.lower().strip()


def parsear_monto(texto: str) -> Decimal | None:
    """Convierte '1,234.56', '1.234,56', '(45.00)' o '45.00-' a Decimal.

    Devuelve None si el texto no es un importe.
    """
    bruto = texto.strip()
    if not bruto:
        return None
    m = RE_MONTO.match(bruto)
    if not m:
        return None

    negativo = bruto.startswith("(") or bruto.endswith(")") or bruto.startswith("-") or bruto.endswith("-")
    numero = m.group(1)

    # El último separador que aparece es el decimal (Perú usa 1,234.56 pero
    # algunos PDFs vienen con formato europeo).
    ultimo_punto = numero.rfind(".")
    ultima_coma = numero.rfind(",")
    if ultima_coma > ultimo_punto:
        numero = numero.replace(".", "").replace(",", ".")
    else:
        numero = numero.replace(",", "")

    try:
        valor = Decimal(numero)
    except InvalidOperation:
        return None
    return -valor if negativo else valor


def parsear_fecha(texto: str, anio_defecto: int) -> date | None:
    """Convierte '15/03/2026', '15/03', '15Mar' o '15 MAR 26' a date.

    El formato peruano es DD/MM/YYYY, así que el primer número siempre es el día.
    """
    bruto = texto.strip()
    if not bruto:
        return None

    iso = RE_FECHA_ISO.match(bruto)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None

    bruto = bruto.replace(" ", "")
    m = RE_FECHA_NUM.match(bruto)
    if m:
        dia, mes, anio = int(m.group(1)), int(m.group(2)), m.group(3)
    else:
        m = RE_FECHA_MES.match(bruto)
        if not m:
            return None
        dia = int(m.group(1))
        mes = MESES_ES[_normalizar(m.group(2))[:3]]
        anio = m.group(3)

    if anio is None:
        anio_int = anio_defecto
    else:
        anio_int = int(anio)
        if anio_int < 100:  # '26' -> 2026
            anio_int += 2000

    try:
        return date(anio_int, mes, dia)
    except ValueError:
        return None


def detectar_banco(texto: str) -> str | None:
    normalizado = _normalizar(texto)
    for banco, pistas in BANCOS.items():
        if any(p in normalizado for p in pistas):
            return banco
    return None


def _detectar_anio(texto: str) -> int:
    """Toma el año más frecuente del documento; si no hay, usa el año actual."""
    anios = RE_ANIO.findall(texto)
    if not anios:
        return date.today().year
    return int(max(set(anios), key=anios.count))


def _es_ruido(descripcion: str) -> bool:
    n = _normalizar(descripcion)
    return any(r in n for r in RUIDO)


def _signo_por_texto(descripcion: str) -> int:
    """Devuelve -1 (gasto), +1 (ingreso) o 0 (no se sabe) según palabras clave."""
    n = _normalizar(descripcion)
    puntaje_gasto = sum(1 for p in PISTAS_GASTO if p in n)
    puntaje_ingreso = sum(1 for p in PISTAS_INGRESO if p in n)
    if puntaje_ingreso > puntaje_gasto:
        return 1
    if puntaje_gasto > puntaje_ingreso:
        return -1
    return 0


# ============================================================ apertura del PDF


def abrir_pdf(contenido: bytes, clave: str | None = None) -> bytes:
    """Devuelve el PDF listo para leer, quitándole la contraseña si la tiene."""
    try:
        with pikepdf.open(io.BytesIO(contenido)) as pdf:
            # No estaba protegido: lo devolvemos tal cual.
            return contenido
    except pikepdf.PasswordError:
        pass
    except Exception as exc:  # PDF corrupto o no es un PDF
        raise ErrorExtraccion(
            f"El archivo no se pudo abrir como PDF: {exc}", "PDF_INVALIDO"
        ) from exc

    if not clave:
        raise PdfProtegidoError(
            "El PDF tiene contraseña y no hay una clave guardada. "
            "Agrega la clave de tus PDFs en tu perfil (normalmente es tu DNI)."
        )

    try:
        with pikepdf.open(io.BytesIO(contenido), password=clave) as pdf:
            salida = io.BytesIO()
            pdf.save(salida)
            return salida.getvalue()
    except pikepdf.PasswordError as exc:
        raise PdfProtegidoError(
            "La clave guardada no abre este PDF. Actualízala en tu perfil "
            "(normalmente es el DNI del titular)."
        ) from exc


# ============================================================ nivel 1: columnas


@dataclass
class _Columna:
    tipo: str          # fecha | descripcion | cargo | abono | monto | saldo
    centro: float


@dataclass
class _FilaCruda:
    fecha: date
    descripcion: str
    cargo: Decimal | None = None
    abono: Decimal | None = None
    monto: Decimal | None = None
    saldo: Decimal | None = None


def _agrupar_en_lineas(palabras: list[dict], tolerancia: float = 3.0) -> list[list[dict]]:
    """Agrupa las palabras de una página en líneas según su coordenada vertical."""
    lineas: list[list[dict]] = []
    for palabra in sorted(palabras, key=lambda w: (round(w["top"], 1), w["x0"])):
        if lineas and abs(lineas[-1][0]["top"] - palabra["top"]) <= tolerancia:
            lineas[-1].append(palabra)
        else:
            lineas.append([palabra])
    for linea in lineas:
        linea.sort(key=lambda w: w["x0"])
    return lineas


def _detectar_columnas(linea: list[dict]) -> list[_Columna] | None:
    """Si la línea es un encabezado de tabla, devuelve sus columnas con posición X."""
    columnas: list[_Columna] = []
    for palabra in linea:
        n = _normalizar(palabra["text"]).replace(".", "").replace(":", "")
        for tipo, alias in CABECERAS.items():
            if n in alias:
                columnas.append(_Columna(tipo, (palabra["x0"] + palabra["x1"]) / 2))
                break

    tipos = {c.tipo for c in columnas}
    # Un encabezado real trae fecha + descripción + al menos una columna de plata
    if "fecha" in tipos and tipos & {"cargo", "abono", "monto", "saldo"}:
        columnas.sort(key=lambda c: c.centro)
        return columnas
    return None


def _asignar_columna(centro_x: float, columnas: list[_Columna]) -> _Columna | None:
    """Devuelve la columna a la que pertenece un importe según su posición X.

    Los números vienen alineados a la derecha bajo su encabezado, así que se usa
    la frontera media entre encabezados consecutivos.
    """
    monetarias = [c for c in columnas if c.tipo in {"cargo", "abono", "monto", "saldo"}]
    if not monetarias:
        return None
    return min(monetarias, key=lambda c: abs(c.centro - centro_x))


def _parsear_pagina_por_columnas(
    lineas: list[list[dict]], anio_defecto: int
) -> list[_FilaCruda]:
    columnas: list[_Columna] | None = None
    filas: list[_FilaCruda] = []

    for linea in lineas:
        posible = _detectar_columnas(linea)
        if posible:
            columnas = posible
            continue
        if columnas is None:
            continue

        texto_linea = " ".join(w["text"] for w in linea)
        fecha = parsear_fecha(linea[0]["text"], anio_defecto)

        if fecha is None:
            # Línea de continuación: pertenece a la descripción del movimiento previo.
            if filas and not any(parsear_monto(w["text"]) for w in linea):
                extra = texto_linea.strip()
                if extra and not _es_ruido(extra):
                    filas[-1].descripcion = f"{filas[-1].descripcion} {extra}".strip()
            continue

        if _es_ruido(texto_linea):
            continue

        fila = _FilaCruda(fecha=fecha, descripcion="")
        partes_descripcion: list[str] = []
        primera_monetaria = min(
            (c.centro for c in columnas if c.tipo in {"cargo", "abono", "monto", "saldo"}),
            default=float("inf"),
        )

        for palabra in linea[1:]:
            centro = (palabra["x0"] + palabra["x1"]) / 2
            valor = parsear_monto(palabra["text"])
            # Solo se trata como importe si además cae en la zona de las columnas de plata
            if valor is not None and centro >= primera_monetaria - 40:
                columna = _asignar_columna(centro, columnas)
                if columna is not None:
                    if columna.tipo == "cargo" and fila.cargo is None:
                        fila.cargo = abs(valor)
                    elif columna.tipo == "abono" and fila.abono is None:
                        fila.abono = abs(valor)
                    elif columna.tipo == "monto" and fila.monto is None:
                        fila.monto = valor
                    elif columna.tipo == "saldo":
                        fila.saldo = valor
                    continue
            # Otra fecha (fecha valor / fecha proceso) no va en la descripción
            if parsear_fecha(palabra["text"], anio_defecto) is not None:
                continue
            partes_descripcion.append(palabra["text"])

        fila.descripcion = " ".join(partes_descripcion).strip()
        if fila.cargo is None and fila.abono is None and fila.monto is None and fila.saldo is None:
            continue
        filas.append(fila)

    return filas


# ============================================================ nivel 3: texto plano


def _parsear_pagina_por_texto(texto: str, anio_defecto: int) -> list[_FilaCruda]:
    """Fallback cuando no se detectó encabezado de tabla: regex línea por línea."""
    filas: list[_FilaCruda] = []
    for linea in texto.splitlines():
        limpia = linea.strip()
        if not limpia or _es_ruido(limpia):
            continue

        tokens = limpia.split()
        fecha = parsear_fecha(tokens[0], anio_defecto)
        if fecha is None:
            if filas and not any(parsear_monto(t) for t in tokens):
                filas[-1].descripcion = f"{filas[-1].descripcion} {limpia}".strip()
            continue

        importes: list[Decimal] = []
        descripcion: list[str] = []
        for token in tokens[1:]:
            valor = parsear_monto(token)
            if valor is not None:
                importes.append(valor)
            elif parsear_fecha(token, anio_defecto) is None:
                descripcion.append(token)

        if not importes:
            continue

        fila = _FilaCruda(fecha=fecha, descripcion=" ".join(descripcion).strip())
        if len(importes) >= 2:
            # El último suele ser el saldo corrido
            fila.monto = importes[-2]
            fila.saldo = importes[-1]
        else:
            fila.monto = importes[0]
        filas.append(fila)

    return filas


# ============================================================ consolidación


def _corregir_signos_por_saldo(filas: list[_FilaCruda]) -> None:
    """Si hay columna de saldo, el signo real es la diferencia entre saldos.

    Es el método más confiable: no depende de encabezados ni de palabras clave.
    Solo se aplica cuando la diferencia coincide con el importe de la fila.
    """
    saldo_previo: Decimal | None = None
    for fila in filas:
        if fila.saldo is None:
            saldo_previo = None
            continue
        if saldo_previo is not None:
            delta = fila.saldo - saldo_previo
            bruto = fila.cargo or fila.abono or (abs(fila.monto) if fila.monto is not None else None)
            if bruto is not None and abs(abs(delta) - bruto) <= Decimal("0.01"):
                fila.monto = delta
                fila.cargo = None
                fila.abono = None
        saldo_previo = fila.saldo


def _a_movimiento(fila: _FilaCruda) -> tuple[date, Decimal, str] | None:
    """Convierte una fila cruda en (fecha, monto con signo, descripción)."""
    descripcion = re.sub(r"\s+", " ", fila.descripcion).strip()
    if not descripcion:
        descripcion = "Movimiento sin descripción"

    if fila.cargo is not None and fila.abono is not None:
        # Ambas columnas con valor: gana la de mayor importe (una suele ser 0.00)
        monto = fila.abono - fila.cargo
    elif fila.cargo is not None:
        monto = -fila.cargo
    elif fila.abono is not None:
        monto = fila.abono
    elif fila.monto is not None:
        monto = fila.monto
        if monto > 0:
            # Sin columnas de cargo/abono el signo se deduce del texto
            signo = _signo_por_texto(descripcion)
            if signo < 0:
                monto = -monto
    else:
        return None

    if monto == 0:
        return None
    return fila.fecha, monto, descripcion


# ============================================================ API pública


@dataclass
class ResultadoExtraccion:
    movimientos: list[dict] = field(default_factory=list)
    banco: str | None = None
    paginas: int = 0

    @property
    def mes_inicio(self) -> date | None:
        return min((m["fecha"] for m in self.movimientos), default=None)

    @property
    def mes_fin(self) -> date | None:
        return max((m["fecha"] for m in self.movimientos), default=None)


def extraer_movimientos_pdf(contenido: bytes, clave: str | None = None) -> ResultadoExtraccion:
    """Lee un PDF de estado de cuenta y devuelve sus movimientos.

    Args:
        contenido: bytes del PDF.
        clave: contraseña del PDF, si tiene (normalmente el DNI del titular).

    Returns:
        ResultadoExtraccion con `movimientos` = [{fecha, monto, descripcion}].

    Raises:
        PdfProtegidoError: el PDF pide clave y la que hay no funciona.
        NoReconocidoError: se abrió, pero no se encontró ningún movimiento.
    """
    datos = abrir_pdf(contenido, clave)
    resultado = ResultadoExtraccion()
    filas: list[_FilaCruda] = []

    with pdfplumber.open(io.BytesIO(datos)) as pdf:
        resultado.paginas = len(pdf.pages)
        texto_completo = "\n".join((p.extract_text() or "") for p in pdf.pages)

        if not texto_completo.strip():
            raise NoReconocidoError(
                "El PDF no tiene texto seleccionable (parece un escaneo). "
                "Descarga el estado de cuenta directamente desde la banca por internet."
            )

        resultado.banco = detectar_banco(texto_completo)
        anio = _detectar_anio(texto_completo)

        for pagina in pdf.pages:
            palabras = pagina.extract_words(keep_blank_chars=False, use_text_flow=False)
            filas_pagina = _parsear_pagina_por_columnas(_agrupar_en_lineas(palabras), anio)
            if not filas_pagina:
                filas_pagina = _parsear_pagina_por_texto(pagina.extract_text() or "", anio)
            filas.extend(filas_pagina)

    _corregir_signos_por_saldo(filas)

    vistos: set[tuple] = set()
    for fila in filas:
        movimiento = _a_movimiento(fila)
        if movimiento is None:
            continue
        fecha, monto, descripcion = movimiento
        clave_dedup = (fecha, monto, descripcion)
        if clave_dedup in vistos:
            continue
        vistos.add(clave_dedup)
        resultado.movimientos.append(
            {"fecha": fecha, "monto": monto, "descripcion": descripcion}
        )

    if not resultado.movimientos:
        raise NoReconocidoError(
            "No se encontraron movimientos en este PDF. "
            "Verifica que sea un estado de cuenta bancario y no un voucher o resumen."
        )

    resultado.movimientos.sort(key=lambda m: m["fecha"])
    logger.info(
        "PDF procesado: banco=%s paginas=%s movimientos=%s",
        resultado.banco, resultado.paginas, len(resultado.movimientos),
    )
    return resultado
