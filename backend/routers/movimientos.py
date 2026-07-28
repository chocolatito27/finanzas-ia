"""Consultas del dashboard: resúmenes, tendencias y proyección de cierre de año.

Regla de negocio clave: **TRANSFERENCIA_INTERNA nunca cuenta** como ingreso ni como
gasto. Es plata que el dueño mueve entre sus propias cuentas; sumarla inflaría
artificialmente ambos lados.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from database import (
    a_decimal,
    actualizar_categoria,
    listar_movimientos,
    todos_los_movimientos,
)
from models import (
    CATEGORIAS_GASTO,
    CATEGORIAS_INGRESO,
    ActualizarCategoriaIn,
    Categoria,
    DashboardOut,
    MovimientoOut,
    PorCategoria,
    Proyeccion,
    PuntoSerie,
    ResumenMes,
    SerieOut,
)
from security import UsuarioAutenticado, usuario_activo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/movimientos", tags=["movimientos"])

CENTAVO = Decimal("0.01")
MESES_TENDENCIA = 6

_INGRESO = {c.value for c in CATEGORIAS_INGRESO}
_GASTO = {c.value for c in CATEGORIAS_GASTO}


def _redondear(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _a_fecha(valor) -> date:
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])


def _clave_mes(fecha: date) -> str:
    return f"{fecha.year:04d}-{fecha.month:02d}"


def _meses_entre(primero: str, ultimo: str) -> list[str]:
    """Todos los meses de 'YYYY-MM' a 'YYYY-MM', incluidos los que no tienen datos."""
    anio, mes = int(primero[:4]), int(primero[5:7])
    anio_fin, mes_fin = int(ultimo[:4]), int(ultimo[5:7])
    meses = []
    while (anio, mes) <= (anio_fin, mes_fin):
        meses.append(f"{anio:04d}-{mes:02d}")
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return meses


def _rellenar_meses(
    por_mes: dict[str, dict[str, Decimal]],
) -> dict[str, dict[str, Decimal]]:
    """Completa con ceros los meses sin movimientos.

    Sin esto, un usuario que sube marzo y junio ve las dos barras pegadas como si
    fueran meses consecutivos: el gráfico miente sobre la tendencia. Un eje de
    tiempo tiene que ser continuo aunque haya huecos.
    """
    if not por_mes:
        return por_mes
    claves = sorted(por_mes)
    completo: dict[str, dict[str, Decimal]] = {}
    for mes in _meses_entre(claves[0], claves[-1]):
        completo[mes] = por_mes.get(
            mes, {"ingresos": Decimal(0), "gastos": Decimal(0)}
        )
    return completo


def _resumen_por_mes(filas: list[dict]) -> dict[str, dict[str, Decimal]]:
    """Agrupa por mes sumando ingresos y gastos, ignorando transferencias internas."""
    acumulado: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"ingresos": Decimal(0), "gastos": Decimal(0)}
    )
    for fila in filas:
        categoria = fila.get("categoria")
        if categoria not in _INGRESO and categoria not in _GASTO:
            continue  # TRANSFERENCIA_INTERNA y DESCONOCIDO no entran al cálculo
        mes = _clave_mes(_a_fecha(fila["fecha"]))
        monto = a_decimal(fila["monto"])
        if categoria in _INGRESO:
            acumulado[mes]["ingresos"] += abs(monto)
        else:
            acumulado[mes]["gastos"] += abs(monto)
    return acumulado


def _a_resumen(mes: str, datos: dict[str, Decimal]) -> ResumenMes:
    ingresos = _redondear(datos["ingresos"])
    gastos = _redondear(datos["gastos"])
    return ResumenMes(mes=mes, ingresos=ingresos, gastos=gastos, balance=ingresos - gastos)


def _calcular_proyeccion(por_mes: dict[str, dict[str, Decimal]]) -> Proyeccion:
    """Extrapolación lineal al cierre del año: promedio mensual × 12.

    Se usa el año del último movimiento (no el año del reloj) para que la proyección
    tenga sentido aunque el usuario suba estados de cuenta atrasados.
    """
    if not por_mes:
        anio = date.today().year
        cero = Decimal("0.00")
        return Proyeccion(
            anio=anio, meses_con_datos=0,
            promedio_ingreso_mensual=cero, promedio_gasto_mensual=cero,
            ingresos_acumulados=cero, gastos_acumulados=cero,
            ingresos_proyectados_cierre=cero, gastos_proyectados_cierre=cero,
            balance_proyectado_cierre=cero, confiable=False,
        )

    anio = max(int(m[:4]) for m in por_mes)
    meses_anio = {m: d for m, d in por_mes.items() if int(m[:4]) == anio}

    ingresos_acumulados = sum((d["ingresos"] for d in meses_anio.values()), Decimal(0))
    gastos_acumulados = sum((d["gastos"] for d in meses_anio.values()), Decimal(0))
    n = len(meses_anio) or 1

    promedio_ingreso = ingresos_acumulados / n
    promedio_gasto = gastos_acumulados / n
    proyectado_ingreso = promedio_ingreso * 12
    proyectado_gasto = promedio_gasto * 12

    return Proyeccion(
        anio=anio,
        meses_con_datos=len(meses_anio),
        promedio_ingreso_mensual=_redondear(promedio_ingreso),
        promedio_gasto_mensual=_redondear(promedio_gasto),
        ingresos_acumulados=_redondear(ingresos_acumulados),
        gastos_acumulados=_redondear(gastos_acumulados),
        ingresos_proyectados_cierre=_redondear(proyectado_ingreso),
        gastos_proyectados_cierre=_redondear(proyectado_gasto),
        balance_proyectado_cierre=_redondear(proyectado_ingreso - proyectado_gasto),
        # Con un solo mes la extrapolación no dice nada útil: se avisa al usuario.
        confiable=len(meses_anio) >= 2,
    )


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(usuario: UsuarioAutenticado = Depends(usuario_activo)) -> DashboardOut:
    """Todos los datos que necesita el dashboard, en una sola llamada."""
    filas = todos_los_movimientos(usuario.id)

    # Dos versiones a propósito:
    #  - por_mes_real: solo meses con movimientos. Es la base de la proyección,
    #    porque un mes vacío significa "no subió el estado de cuenta", no
    #    "facturó cero", y meterlo al promedio lo hundiría.
    #  - por_mes: con los huecos rellenados en cero, para que el eje de tiempo
    #    de los gráficos sea continuo.
    por_mes_real = _resumen_por_mes(filas)
    por_mes = _rellenar_meses(por_mes_real)
    meses_ordenados = sorted(por_mes)
    resumen_mensual = [_a_resumen(m, por_mes[m]) for m in meses_ordenados]

    # "Mes actual" = el mes más reciente con datos (no el del calendario, que puede
    # estar vacío si el usuario aún no subió el estado de cuenta del mes).
    if resumen_mensual:
        mes_actual = resumen_mensual[-1]
    else:
        cero = Decimal("0.00")
        mes_actual = ResumenMes(
            mes=_clave_mes(date.today()), ingresos=cero, gastos=cero, balance=cero
        )

    # Totales por categoría (incluye TRANSFERENCIA_INTERNA y DESCONOCIDO para que el
    # usuario vea qué hay ahí, aunque no entren en ingresos/gastos).
    totales: dict[str, list] = defaultdict(lambda: [Decimal(0), 0])
    for fila in filas:
        categoria = fila.get("categoria") or Categoria.DESCONOCIDO.value
        totales[categoria][0] += abs(a_decimal(fila["monto"]))
        totales[categoria][1] += 1

    por_categoria = sorted(
        (
            PorCategoria(categoria=c, total=_redondear(t[0]), cantidad=t[1])
            for c, t in totales.items()
        ),
        key=lambda p: p.total,
        reverse=True,
    )

    return DashboardOut(
        mes_actual=mes_actual,
        resumen_mensual=resumen_mensual,
        tendencia_ingresos=resumen_mensual[-MESES_TENDENCIA:],
        por_categoria=por_categoria,
        proyeccion=_calcular_proyeccion(por_mes_real),
        total_movimientos=len(filas),
        movimientos_desconocidos=sum(
            1 for f in filas if f.get("categoria") == Categoria.DESCONOCIDO.value
        ),
    )


MESES_CORTOS = [
    "Ene", "Feb", "Mar", "Abr", "May", "Jun",
    "Jul", "Ago", "Set", "Oct", "Nov", "Dic",
]
MAX_PUNTOS_DIARIOS = 400  # ~13 meses; más que eso no se lee en pantalla


def _inicio_periodo(fecha: date, granularidad: str) -> date:
    if granularidad == "mes":
        return fecha.replace(day=1)
    if granularidad == "semana":
        return fecha - timedelta(days=fecha.weekday())  # lunes de esa semana
    return fecha


def _siguiente_periodo(inicio: date, granularidad: str) -> date:
    if granularidad == "mes":
        return date(inicio.year + (inicio.month == 12), (inicio.month % 12) + 1, 1)
    if granularidad == "semana":
        return inicio + timedelta(days=7)
    return inicio + timedelta(days=1)


def _etiquetar(inicio: date, granularidad: str) -> tuple[str, str]:
    """Devuelve (clave, etiqueta) del periodo."""
    if granularidad == "mes":
        return f"{inicio.year:04d}-{inicio.month:02d}", f"{MESES_CORTOS[inicio.month - 1]} {inicio.year}"
    if granularidad == "semana":
        return inicio.isoformat(), f"{inicio.day:02d} {MESES_CORTOS[inicio.month - 1]}"
    return inicio.isoformat(), f"{inicio.day:02d} {MESES_CORTOS[inicio.month - 1]}"


@router.get("/serie", response_model=SerieOut)
async def serie_temporal(
    granularidad: str = Query(default="mes", pattern="^(dia|semana|mes)$"),
    usuario: UsuarioAutenticado = Depends(usuario_activo),
) -> SerieOut:
    """Serie temporal continua de ingresos, gastos, balance y balance acumulado.

    Los periodos sin movimientos van en cero: el eje de tiempo nunca salta, así
    un hueco se lee como un hueco y no como dos fechas consecutivas.
    """
    filas = todos_los_movimientos(usuario.id)
    if not filas:
        return SerieOut(granularidad=granularidad, puntos=[])

    acumulados: dict[date, dict[str, Decimal]] = defaultdict(
        lambda: {"ingresos": Decimal(0), "gastos": Decimal(0)}
    )
    for fila in filas:
        categoria = fila.get("categoria")
        if categoria not in _INGRESO and categoria not in _GASTO:
            continue  # las transferencias internas no son ingreso ni gasto
        inicio = _inicio_periodo(_a_fecha(fila["fecha"]), granularidad)
        monto = abs(a_decimal(fila["monto"]))
        clave = "ingresos" if categoria in _INGRESO else "gastos"
        acumulados[inicio][clave] += monto

    if not acumulados:
        return SerieOut(granularidad=granularidad, puntos=[])

    inicio, fin = min(acumulados), max(acumulados)

    # En diario, una serie muy larga se vuelve ilegible: se recorta a lo reciente.
    if granularidad == "dia" and (fin - inicio).days > MAX_PUNTOS_DIARIOS:
        inicio = fin - timedelta(days=MAX_PUNTOS_DIARIOS)

    puntos: list[PuntoSerie] = []
    corrido = Decimal(0)
    actual = inicio
    while actual <= fin:
        datos = acumulados.get(actual, {"ingresos": Decimal(0), "gastos": Decimal(0)})
        ingresos = _redondear(datos["ingresos"])
        gastos = _redondear(datos["gastos"])
        balance = ingresos - gastos
        corrido += balance
        clave, etiqueta = _etiquetar(actual, granularidad)
        puntos.append(
            PuntoSerie(
                periodo=clave,
                etiqueta=etiqueta,
                ingresos=ingresos,
                gastos=gastos,
                balance=balance,
                acumulado=_redondear(corrido),
            )
        )
        actual = _siguiente_periodo(actual, granularidad)

    return SerieOut(granularidad=granularidad, puntos=puntos)


@router.get("", response_model=list[MovimientoOut])
async def lista_movimientos(
    categoria: str | None = Query(default=None, description="Filtrar por categoría"),
    mes: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$", description="YYYY-MM"),
    limite: int = Query(default=500, ge=1, le=2000),
    usuario: UsuarioAutenticado = Depends(usuario_activo),
) -> list[MovimientoOut]:
    """Tabla de movimientos con filtros por categoría y mes."""
    if categoria and categoria not in {c.value for c in Categoria}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Categoría inválida: {categoria}")

    filas = listar_movimientos(usuario.id, categoria=categoria, mes=mes, limite=limite)
    return [
        MovimientoOut(
            id=f["id"],
            fecha=_a_fecha(f["fecha"]),
            monto=a_decimal(f["monto"]),
            descripcion_original=f.get("descripcion_original"),
            descripcion_limpia=f.get("descripcion_limpia"),
            categoria=f.get("categoria") or Categoria.DESCONOCIDO.value,
        )
        for f in filas
    ]


@router.patch("/{movimiento_id}/categoria", response_model=dict)
async def corregir_categoria(
    movimiento_id: str,
    datos: ActualizarCategoriaIn,
    usuario: UsuarioAutenticado = Depends(usuario_activo),
) -> dict:
    """Permite al usuario corregir un movimiento que la IA clasificó mal."""
    if not actualizar_categoria(usuario.id, movimiento_id, datos.categoria.value):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Movimiento no encontrado")
    return {"ok": True, "categoria": datos.categoria.value}
