import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

/* ============================================================
   Formato peruano: Soles y fechas DD/MM/YYYY
   ============================================================ */

const formateadorSoles = new Intl.NumberFormat('es-PE', {
  style: 'currency',
  currency: 'PEN',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

/** 1234.5 → "S/ 1,234.50" */
export function soles(valor) {
  const numero = Number(valor ?? 0)
  return formateadorSoles.format(Number.isFinite(numero) ? numero : 0)
}

/** 1234.5 → "S/ 1.2K" — para ejes de gráficos donde no cabe el número completo */
export function solesCorto(valor) {
  const numero = Number(valor ?? 0)
  const abs = Math.abs(numero)
  if (abs >= 1_000_000) return `S/ ${(numero / 1_000_000).toFixed(1)}M`
  if (abs >= 1_000) return `S/ ${(numero / 1_000).toFixed(1)}K`
  return `S/ ${numero.toFixed(0)}`
}

/** "2026-03-15" → "15/03/2026" (sin desfase por zona horaria) */
export function fechaPeru(iso) {
  if (!iso) return ''
  const [anio, mes, dia] = String(iso).slice(0, 10).split('-')
  return `${dia}/${mes}/${anio}`
}

const NOMBRES_MES = [
  'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
  'Jul', 'Ago', 'Set', 'Oct', 'Nov', 'Dic',
]

/** "2026-03" → "Mar 2026" */
export function etiquetaMes(clave) {
  if (!clave) return ''
  const [anio, mes] = clave.split('-')
  return `${NOMBRES_MES[Number(mes) - 1] ?? mes} ${anio}`
}

/** "2026-03" → "Mar" — para ejes de gráficos */
export function mesCorto(clave) {
  if (!clave) return ''
  const [, mes] = clave.split('-')
  return NOMBRES_MES[Number(mes) - 1] ?? clave
}

/* ============================================================
   Categorías: etiquetas en español y colores
   ============================================================ */

export const CATEGORIAS = {
  INGRESO_VENTA: {
    etiqueta: 'Venta',
    descripcion: 'Entrada de dinero por ventas',
    color: '#10b981',
    tipo: 'ingreso',
  },
  INGRESO_TRANSFERENCIA: {
    etiqueta: 'Transferencia recibida',
    descripcion: 'Transferencia recibida de otra persona',
    color: '#34d399',
    tipo: 'ingreso',
  },
  GASTO_PROVEEDOR: {
    etiqueta: 'Proveedor',
    descripcion: 'Pago a proveedores o compra de stock',
    color: '#ef4444',
    tipo: 'gasto',
  },
  GASTO_OPERATIVO: {
    etiqueta: 'Operativo',
    descripcion: 'Alquiler, servicios, luz, internet',
    color: '#f97316',
    tipo: 'gasto',
  },
  GASTO_PERSONAL: {
    etiqueta: 'Personal',
    descripcion: 'Retiro personal del dueño',
    color: '#f59e0b',
    tipo: 'gasto',
  },
  TRANSFERENCIA_INTERNA: {
    etiqueta: 'Entre cuentas propias',
    descripcion: 'No cuenta como ingreso ni gasto',
    color: '#6366f1',
    tipo: 'neutro',
  },
  DESCONOCIDO: {
    etiqueta: 'Sin clasificar',
    descripcion: 'Revísalo y corrígelo tú',
    color: '#64748b',
    tipo: 'neutro',
  },
}

export const LISTA_CATEGORIAS = Object.keys(CATEGORIAS)

export function infoCategoria(clave) {
  return CATEGORIAS[clave] ?? CATEGORIAS.DESCONOCIDO
}
