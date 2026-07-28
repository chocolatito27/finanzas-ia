/**
 * Totales por categoría — barras horizontales ordenadas de mayor a menor.
 *
 * A propósito NO es un gráfico de torta ni usa un color por categoría: con 7
 * categorías, siete colores obligan al lector a ir y volver a una leyenda, y no
 * hay siete tonos que se distingan bien con daltonismo. El nombre va en el eje y
 * la longitud de la barra hace todo el trabajo; el color solo marca si es
 * ingreso, gasto o neutro (3 estados, cada uno etiquetado).
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { infoCategoria, soles, solesCorto } from '@/lib/utils'
import { COLORES, ejeComun, estiloTooltip } from './tema'

const COLOR_POR_TIPO = {
  ingreso: COLORES.ingreso,
  gasto: COLORES.gasto,
  neutro: COLORES.acento,
}

function TooltipCategoria({ active, payload }) {
  if (!active || !payload?.length) return null
  const fila = payload[0].payload
  return (
    <div style={estiloTooltip.contentStyle}>
      <div style={estiloTooltip.labelStyle}>{fila.etiqueta}</div>
      <div className="font-mono text-foreground tabular">{soles(fila.total)}</div>
      <div className="text-xs text-muted-foreground mt-1">
        {fila.cantidad} movimiento{fila.cantidad === 1 ? '' : 's'}
      </div>
    </div>
  )
}

export default function GastosPorCategoria({ datos = [] }) {
  if (!datos.length) {
    return (
      <p className="text-sm text-muted-foreground py-12 text-center">
        Aún no hay movimientos categorizados.
      </p>
    )
  }

  const filas = datos
    .map((d) => {
      const info = infoCategoria(d.categoria)
      return {
        categoria: d.categoria,
        etiqueta: info.etiqueta,
        tipo: info.tipo,
        total: Number(d.total),
        cantidad: d.cantidad,
      }
    })
    .sort((a, b) => b.total - a.total)

  return (
    <ResponsiveContainer width="100%" height={Math.max(220, filas.length * 42)}>
      <BarChart
        data={filas}
        layout="vertical"
        margin={{ top: 4, right: 16, bottom: 4, left: 0 }}
      >
        <CartesianGrid stroke={COLORES.grilla} strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" tickFormatter={solesCorto} {...ejeComun} />
        <YAxis
          type="category"
          dataKey="etiqueta"
          width={150}
          {...ejeComun}
          tick={{ fill: COLORES.tintaSuave, fontSize: 12 }}
        />
        <Tooltip content={<TooltipCategoria />} cursor={estiloTooltip.cursor} />
        <Bar
          dataKey="total"
          radius={[0, 4, 4, 0]}
          maxBarSize={22}
          isAnimationActive={false}
        >
          {filas.map((fila) => (
            <Cell key={fila.categoria} fill={COLOR_POR_TIPO[fila.tipo] ?? COLORES.acento} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
