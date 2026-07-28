/**
 * Ingresos vs gastos por mes — barras agrupadas.
 *
 * Dos series de orden fijo (ingresos siempre a la izquierda) con leyenda y tooltip
 * que nombra cada una: la identidad nunca depende solo del color.
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { etiquetaMes, mesCorto, soles, solesCorto } from '@/lib/utils'
import { COLORES, ejeComun, estiloTooltip } from './tema'

function TooltipBarras({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div style={estiloTooltip.contentStyle}>
      <div style={estiloTooltip.labelStyle}>{etiquetaMes(label)}</div>
      {payload.map((serie) => (
        <div key={serie.dataKey} className="flex items-center gap-2 tabular">
          <span
            className="inline-block size-2.5 rounded-sm shrink-0"
            style={{ background: serie.color }}
          />
          <span className="text-muted-foreground">{serie.name}</span>
          <span className="ml-auto font-mono text-foreground">{soles(serie.value)}</span>
        </div>
      ))}
    </div>
  )
}

function Leyenda({ color, texto }) {
  return (
    <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
      <span
        className="inline-block size-2.5 rounded-sm shrink-0"
        style={{ background: color }}
      />
      {texto}
    </span>
  )
}

export default function GraficoBarras({ datos = [] }) {
  if (!datos.length) {
    return (
      <p className="text-sm text-muted-foreground py-12 text-center">
        Sube un estado de cuenta para ver este gráfico.
      </p>
    )
  }

  return (
    <>
      {/* La leyenda va como HTML y no con <Legend> de Recharts: Recharts ignora
          el orden que se le pasa y la deja al revés que las barras, lo que
          confunde justo en el punto donde el color hace el trabajo. */}
      <div className="mb-3 flex items-center gap-4">
        <Leyenda color={COLORES.ingreso} texto="Ingresos" />
        <Leyenda color={COLORES.gasto} texto="Gastos" />
      </div>

      <ResponsiveContainer width="100%" height={280}>
      <BarChart data={datos} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barGap={2}>
        <CartesianGrid stroke={COLORES.grilla} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="mes" tickFormatter={mesCorto} {...ejeComun} />
        <YAxis tickFormatter={solesCorto} width={68} {...ejeComun} />
        <Tooltip content={<TooltipBarras />} cursor={estiloTooltip.cursor} />
        <Bar
          dataKey="ingresos"
          name="Ingresos"
          fill={COLORES.ingreso}
          radius={[4, 4, 0, 0]}
          maxBarSize={26}
          isAnimationActive={false}
        />
        <Bar
          dataKey="gastos"
          name="Gastos"
          fill={COLORES.gasto}
          radius={[4, 4, 0, 0]}
          maxBarSize={26}
          isAnimationActive={false}
        />
      </BarChart>
      </ResponsiveContainer>
    </>
  )
}
