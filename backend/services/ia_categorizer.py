"""Categorización de movimientos bancarios usando Venice AI (modelos Claude).

Venice expone una API compatible con OpenAI, así que se usa el SDK `openai`
apuntando a su base URL.

Decisiones de diseño:

* **Lotes de 40 movimientos.** Un estado de cuenta puede traer cientos de líneas;
  mandarlas todas en un prompt agota el contexto y encarece la llamada. Además, si
  un lote falla, solo se degradan esos 40 y no el archivo completo.
* **Hasta 2 reintentos por lote** cuando el modelo devuelve JSON inválido, tal como
  pide el brief. Si igual falla, esos movimientos quedan como DESCONOCIDO en vez de
  perderse.
* **El monto y la fecha nunca vienen del modelo.** Se conservan los valores del
  extractor y del modelo solo se toman `categoria` y `descripcion_limpia`. Así una
  alucinación no puede corromper las cifras del dashboard.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from decimal import Decimal

from openai import AsyncOpenAI

from config import settings
from models import Categoria, MovimientoCategorizado

logger = logging.getLogger(__name__)

TAMANIO_LOTE = 40
MAX_REINTENTOS = 2
CONCURRENCIA_LOTES = 3

SYSTEM_PROMPT = """Eres un asistente contable para pequeños negocios peruanos.
Tu tarea es categorizar movimientos bancarios.

Para cada movimiento recibirás: fecha, monto (positivo=ingreso, negativo=gasto), y descripción del banco.

Responde SOLO con un JSON array con este formato exacto, sin texto extra:
[
  {
    "i": 0,
    "categoria": "INGRESO_VENTA",
    "descripcion_limpia": "Transferencia de Henris SAC"
  }
]

El campo "i" es el índice del movimiento tal como te lo envié: devuélvelo igual y en el mismo orden.
"descripcion_limpia" es la descripción del banco reescrita en español claro, corta (máximo 60 caracteres), sin códigos ni abreviaturas del banco.

Categorías disponibles: INGRESO_VENTA, INGRESO_TRANSFERENCIA, GASTO_PROVEEDOR, GASTO_OPERATIVO, GASTO_PERSONAL, TRANSFERENCIA_INTERNA, DESCONOCIDO.

Reglas:
- Un monto positivo solo puede ser INGRESO_VENTA, INGRESO_TRANSFERENCIA o TRANSFERENCIA_INTERNA.
- Un monto negativo solo puede ser GASTO_PROVEEDOR, GASTO_OPERATIVO, GASTO_PERSONAL o TRANSFERENCIA_INTERNA.
- Si el movimiento es entre cuentas del mismo titular (dice "cuenta propia", "ahorros", "traspaso", el mismo nombre del titular), usa TRANSFERENCIA_INTERNA.
- Comisiones, ITF, portes, mantenimiento, luz, agua, internet, alquiler → GASTO_OPERATIVO.
- Compras de mercadería, pagos a proveedores e importaciones → GASTO_PROVEEDOR.
- Retiros de efectivo o consumos claramente personales del dueño → GASTO_PERSONAL.
- Si no está claro, usa DESCONOCIDO. Es preferible DESCONOCIDO a inventar.

Responde siempre en JSON válido, sin markdown ni explicaciones."""


def _cliente() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.venice_api_key,
        base_url=settings.venice_base_url,
        timeout=120.0,
        max_retries=1,  # reintentos de red; los de JSON inválido se manejan aparte
    )


def _extraer_json(texto: str) -> list | None:
    """Saca el array JSON de la respuesta aunque venga envuelto en markdown."""
    if not texto:
        return None
    limpio = texto.strip()

    # ```json ... ```
    valla = re.search(r"```(?:json)?\s*(.+?)\s*```", limpio, re.DOTALL)
    if valla:
        limpio = valla.group(1).strip()

    try:
        datos = json.loads(limpio)
    except json.JSONDecodeError:
        # Último intento: recortar desde el primer '[' hasta el último ']'
        inicio, fin = limpio.find("["), limpio.rfind("]")
        if inicio == -1 or fin <= inicio:
            return None
        try:
            datos = json.loads(limpio[inicio : fin + 1])
        except json.JSONDecodeError:
            return None

    if isinstance(datos, dict):
        # A veces el modelo envuelve el array en {"movimientos": [...]}
        for valor in datos.values():
            if isinstance(valor, list):
                return valor
        return None
    return datos if isinstance(datos, list) else None


def _categoria_valida(valor: object, monto: Decimal) -> Categoria:
    """Valida la categoría del modelo y la corrige si contradice el signo del monto."""
    try:
        categoria = Categoria(str(valor).strip().upper())
    except (ValueError, AttributeError):
        return Categoria.DESCONOCIDO

    es_ingreso = categoria in {Categoria.INGRESO_VENTA, Categoria.INGRESO_TRANSFERENCIA}
    es_gasto = categoria in {
        Categoria.GASTO_PROVEEDOR,
        Categoria.GASTO_OPERATIVO,
        Categoria.GASTO_PERSONAL,
    }
    # El signo lo decide el banco, no el modelo: si se contradicen, gana el banco.
    if monto > 0 and es_gasto:
        return Categoria.DESCONOCIDO
    if monto < 0 and es_ingreso:
        return Categoria.DESCONOCIDO
    return categoria


def _armar_payload(lote: list[dict]) -> str:
    filas = [
        {
            "i": indice,
            "fecha": m["fecha"].isoformat(),
            "monto": float(m["monto"]),
            "descripcion": m["descripcion"][:200],
        }
        for indice, m in enumerate(lote)
    ]
    return json.dumps(filas, ensure_ascii=False)


def _sin_categorizar(lote: list[dict]) -> list[MovimientoCategorizado]:
    """Fallback: todo DESCONOCIDO conservando los datos reales del banco."""
    return [
        MovimientoCategorizado(
            fecha=m["fecha"],
            monto=m["monto"],
            descripcion_original=m["descripcion"],
            descripcion_limpia=m["descripcion"][:120],
            categoria=Categoria.DESCONOCIDO,
        )
        for m in lote
    ]


async def _categorizar_lote(
    cliente: AsyncOpenAI, lote: list[dict], numero_lote: int
) -> list[MovimientoCategorizado]:
    ultimo_error: str | None = None

    for intento in range(1, MAX_REINTENTOS + 2):  # 1 intento + MAX_REINTENTOS
        try:
            respuesta = await cliente.chat.completions.create(
                model=settings.venice_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _armar_payload(lote)},
                ],
                temperature=0,
                max_tokens=8000,
            )
            contenido = respuesta.choices[0].message.content or ""
            datos = _extraer_json(contenido)

            if datos is None:
                ultimo_error = "el modelo no devolvió JSON válido"
                logger.warning(
                    "Lote %s intento %s: JSON inválido. Respuesta: %.200s",
                    numero_lote, intento, contenido,
                )
                continue

            # Indexar por 'i' para no depender del orden de la respuesta
            por_indice: dict[int, dict] = {}
            for item in datos:
                if not isinstance(item, dict):
                    continue
                try:
                    por_indice[int(item.get("i"))] = item
                except (TypeError, ValueError):
                    continue

            if not por_indice:
                ultimo_error = "la respuesta no traía índices utilizables"
                continue

            resultado: list[MovimientoCategorizado] = []
            for indice, movimiento in enumerate(lote):
                item = por_indice.get(indice, {})
                limpia = str(item.get("descripcion_limpia") or "").strip()
                resultado.append(
                    MovimientoCategorizado(
                        fecha=movimiento["fecha"],
                        monto=movimiento["monto"],
                        descripcion_original=movimiento["descripcion"],
                        descripcion_limpia=(limpia or movimiento["descripcion"])[:120],
                        categoria=_categoria_valida(item.get("categoria"), movimiento["monto"]),
                    )
                )

            faltantes = len(lote) - len(por_indice)
            if faltantes > 0:
                logger.warning("Lote %s: %s movimientos sin respuesta del modelo", numero_lote, faltantes)
            return resultado

        except Exception as exc:  # error de red, rate limit, timeout...
            ultimo_error = str(exc)
            logger.warning("Lote %s intento %s falló: %s", numero_lote, intento, exc)
            if intento <= MAX_REINTENTOS:
                await asyncio.sleep(2 * intento)  # backoff simple

    logger.error(
        "Lote %s agotó los reintentos (%s). Se marcan %s movimientos como DESCONOCIDO",
        numero_lote, ultimo_error, len(lote),
    )
    return _sin_categorizar(lote)


async def categorizar_movimientos(movimientos: list[dict]) -> list[MovimientoCategorizado]:
    """Categoriza una lista de movimientos crudos con Venice/Claude.

    Args:
        movimientos: [{fecha: date, monto: Decimal, descripcion: str}]

    Returns:
        Los mismos movimientos con categoría y descripción limpia. Nunca lanza
        excepción por culpa de la IA: si falla, devuelve todo como DESCONOCIDO.
    """
    if not movimientos:
        return []

    if not settings.venice_api_key:
        logger.error("VENICE_API_KEY no configurada: se omite la categorización")
        return _sin_categorizar(movimientos)

    lotes = [
        movimientos[i : i + TAMANIO_LOTE]
        for i in range(0, len(movimientos), TAMANIO_LOTE)
    ]
    logger.info("Categorizando %s movimientos en %s lote(s)", len(movimientos), len(lotes))

    cliente = _cliente()
    semaforo = asyncio.Semaphore(CONCURRENCIA_LOTES)

    async def procesar(indice: int, lote: list[dict]):
        async with semaforo:
            return await _categorizar_lote(cliente, lote, indice + 1)

    try:
        resultados = await asyncio.gather(
            *(procesar(i, lote) for i, lote in enumerate(lotes))
        )
    finally:
        await cliente.close()

    return [movimiento for grupo in resultados for movimiento in grupo]
