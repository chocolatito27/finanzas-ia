"""Modelos Pydantic compartidos por toda la API."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, PlainSerializer

# Pydantic serializa Decimal como string ("15730.00") para no perder precisión.
# Eso rompe los gráficos del frontend, que necesitan números. Los montos se
# guardan y se calculan como Decimal, y solo al salir a JSON se convierten a
# número; la precisión de los cálculos no se toca.
Monto = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float, when_used="json"),
]


class Categoria(str, Enum):
    INGRESO_VENTA = "INGRESO_VENTA"
    INGRESO_TRANSFERENCIA = "INGRESO_TRANSFERENCIA"
    GASTO_PROVEEDOR = "GASTO_PROVEEDOR"
    GASTO_OPERATIVO = "GASTO_OPERATIVO"
    GASTO_PERSONAL = "GASTO_PERSONAL"
    TRANSFERENCIA_INTERNA = "TRANSFERENCIA_INTERNA"
    DESCONOCIDO = "DESCONOCIDO"


CATEGORIAS_INGRESO = {Categoria.INGRESO_VENTA, Categoria.INGRESO_TRANSFERENCIA}
CATEGORIAS_GASTO = {
    Categoria.GASTO_PROVEEDOR,
    Categoria.GASTO_OPERATIVO,
    Categoria.GASTO_PERSONAL,
}


# ---------------------------------------------------------------- extracción


class MovimientoCrudo(BaseModel):
    """Lo que devuelven los extractores de PDF/Excel, antes de pasar por la IA."""

    fecha: date
    monto: Monto
    descripcion: str


class MovimientoCategorizado(BaseModel):
    """Un movimiento ya clasificado por la IA."""

    fecha: date
    monto: Monto
    descripcion_original: str
    descripcion_limpia: str
    categoria: Categoria = Categoria.DESCONOCIDO


# ---------------------------------------------------------------- perfil


class PerfilOut(BaseModel):
    id: str
    email: str | None = None
    nombre_negocio: str | None = None
    activo: bool = False
    onboarding_completo: bool = False
    tiene_clave_pdf: bool = False
    es_admin: bool = False
    created_at: datetime | None = None


class OnboardingIn(BaseModel):
    nombre_negocio: str = Field(min_length=1, max_length=120)
    clave_pdf: str | None = Field(default=None, max_length=64)


class ClavePdfIn(BaseModel):
    """Actualizar solo la clave de los PDFs, sin tocar el nombre del negocio."""

    clave_pdf: str = Field(min_length=1, max_length=64)


# ---------------------------------------------------------------- archivos


class ArchivoResultado(BaseModel):
    nombre_archivo: str
    ok: bool
    banco_detectado: str | None = None
    movimientos_insertados: int = 0
    mes_inicio: date | None = None
    mes_fin: date | None = None
    error: str | None = None
    codigo_error: str | None = None  # PDF_PROTEGIDO | NO_RECONOCIDO | DUPLICADO | ...


class SubidaRespuesta(BaseModel):
    resultados: list[ArchivoResultado]
    total_movimientos: int


# ---------------------------------------------------------------- dashboard


class MovimientoOut(BaseModel):
    id: str
    fecha: date
    monto: Monto
    descripcion_original: str | None = None
    descripcion_limpia: str | None = None
    categoria: str


class ResumenMes(BaseModel):
    mes: str  # "2026-03"
    ingresos: Monto
    gastos: Monto
    balance: Monto


class PorCategoria(BaseModel):
    categoria: str
    total: Monto
    cantidad: int


class Proyeccion(BaseModel):
    """Extrapolación lineal simple al cierre del año en curso."""

    anio: int
    meses_con_datos: int
    promedio_ingreso_mensual: Monto
    promedio_gasto_mensual: Monto
    ingresos_acumulados: Monto
    gastos_acumulados: Monto
    ingresos_proyectados_cierre: Monto
    gastos_proyectados_cierre: Monto
    balance_proyectado_cierre: Monto
    confiable: bool  # False si hay menos de 2 meses de datos


class DashboardOut(BaseModel):
    mes_actual: ResumenMes
    resumen_mensual: list[ResumenMes]
    tendencia_ingresos: list[ResumenMes]
    por_categoria: list[PorCategoria]
    proyeccion: Proyeccion
    total_movimientos: int
    movimientos_desconocidos: int


class PuntoSerie(BaseModel):
    """Un punto de la serie temporal (día, semana o mes)."""

    periodo: str            # "2026-06-14" (día o lunes de la semana) | "2026-06" (mes)
    etiqueta: str           # texto listo para el eje
    ingresos: Monto
    gastos: Monto
    balance: Monto
    acumulado: Monto        # balance acumulado desde el inicio de la serie


class SerieOut(BaseModel):
    granularidad: str       # dia | semana | mes
    puntos: list[PuntoSerie]


class ActualizarCategoriaIn(BaseModel):
    categoria: Categoria


# ---------------------------------------------------------------- admin


class UsuarioAdmin(BaseModel):
    id: str
    email: str | None = None
    nombre_negocio: str | None = None
    activo: bool
    onboarding_completo: bool
    total_movimientos: int = 0
    created_at: datetime | None = None


class CambiarEstadoIn(BaseModel):
    activo: bool
