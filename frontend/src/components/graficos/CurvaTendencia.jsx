/**
 * Curva de tendencia con granularidad ajustable.
 *
 * Antes era una línea de 6 puntos mensuales, que con dos meses de datos se veía
 * como una recta y no decía nada. Ahora:
 *
 *  - **Granularidad diaria, semanal o mensual.** Un estado de cuenta trae ~150
 *    movimientos al mes, así que en diario hay resolución de sobra.
 *  - **Media móvil.** La línea cruda de un negocio es ruidosa (un pago grande
 *    dispara un día); la media móvil es la que deja ver hacia dónde va.
 *  - **Balance acumulado.** El equivalente a una curva de equity: cuánto capital
 *    llevas ganado o perdido desde el inicio del periodo.
 *  - **Brush para hacer zoom** en un tramo, sin perder el contexto del total.
 *
 * Los periodos sin movimientos vienen del backend en cero, así que el eje de
 * tiempo es continuo: un hueco se ve como un hueco.
 */

import { useEffect, useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'
import {
  Area,
  Brush,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { api } from '@/lib/api'
import { cn, soles, solesCorto } from '@/lib/utils'
import { COLORES, ejeComun, estiloTooltip } from './tema'

const GRANULARIDADES = [
  { valor: 'dia', etiqueta: 'Diario' },
  { valor: 'semana', etiqueta: 'Semanal' },
  { valor: 'mes', etiqueta: 'Mensual' },
]

const METRICAS = [
  { valor: 'ingresos', etiqueta: 'Ingresos' },
  { valor: 'balance', etiqueta: 'Balance' },
  { valor: 'acumulado', etiqueta: 'Acumulado' },
]

// Ventana de la media móvil según granularidad: una semana en diario, un mes en
// semanal, un trimestre en mensual. La etiqueta va en palabras ("últimos 7 días")
// y no en jerga ("media 7p"): quien lee esto lleva una tienda, no un fondo.
const VENTANA = {
  dia: { periodos: 7, etiqueta: 'Promedio 7 días', corta: '7 días' },
  semana: { periodos: 4, etiqueta: 'Promedio 4 semanas', corta: '4 semanas' },
  mes: { periodos: 3, etiqueta: 'Promedio 3 meses', corta: '3 meses' },
}

/**
 * Media móvil: cada punto es el promedio de los `ventana` periodos anteriores.
 *
 * Los primeros `ventana - 1` puntos quedan en null porque todavía no hay tantos
 * periodos que promediar — eso es inevitable, no un bug. Lo que sí importa es
 * *cuánto* del gráfico se come: con 120 días y ventana 7 son 6 puntos y no se
 * nota; con 4 meses y ventana 3 son 2 de 4 y la línea arranca a mitad del
 * gráfico, donde estorba más de lo que informa. Por eso `hayDatosSuficientes`
 * decide si vale la pena dibujarla.
 */
function mediaMovil(puntos, campo, ventana) {
  return puntos.map((punto, indice) => {
    if (indice < ventana - 1) return { ...punto, media: null }
    let suma = 0
    for (let i = indice - ventana + 1; i <= indice; i += 1) {
      suma += Number(puntos[i][campo]) || 0
    }
    return { ...punto, media: suma / ventana }
  })
}

/** Se exige el doble de la ventana para que la línea cubra al menos la mitad. */
function hayDatosSuficientes(totalPuntos, ventana) {
  return totalPuntos >= ventana * 2
}

function Segmentado({ opciones, valor, onChange, aria }) {
  return (
    <div
      role="group"
      aria-label={aria}
      className="inline-flex rounded-lg border border-white/10 bg-white/3 p-0.5"
    >
      {opciones.map((o) => (
        <button
          key={o.valor}
          type="button"
          onClick={() => onChange(o.valor)}
          aria-pressed={valor === o.valor}
          className={cn(
            'rounded-md px-2.5 py-1 text-xs transition-colors',
            valor === o.valor
              ? 'bg-white/10 text-foreground'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {o.etiqueta}
        </button>
      ))}
    </div>
  )
}

function Leyenda({ color, texto, punteada = false }) {
  return (
    <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
      <svg width="16" height="4" aria-hidden="true" className="shrink-0">
        <line
          x1="0"
          y1="2"
          x2="16"
          y2="2"
          stroke={color}
          strokeWidth="2"
          strokeDasharray={punteada ? '4 3' : undefined}
        />
      </svg>
      {texto}
    </span>
  )
}

function TooltipCurva({ active, payload, etiquetaMetrica, ventana }) {
  if (!active || !payload?.length) return null
  const fila = payload[0].payload
  return (
    <div style={estiloTooltip.contentStyle}>
      <div style={estiloTooltip.labelStyle}>{fila.etiqueta}</div>
      <div className="flex items-center gap-3 tabular">
        <span className="text-muted-foreground">{etiquetaMetrica}</span>
        <span className="ml-auto font-mono text-foreground">{soles(fila.valor)}</span>
      </div>
      {fila.media != null && (
        <div className="flex items-center gap-3 tabular">
          <span className="text-muted-foreground">Promedio {ventana.corta}</span>
          <span className="ml-auto font-mono" style={{ color: COLORES.media }}>
            {soles(fila.media)}
          </span>
        </div>
      )}
      {fila.valor !== fila.ingresos && (
        <div className="mt-1.5 border-t border-white/10 pt-1.5 text-xs text-muted-foreground tabular">
          Ingresos {soles(fila.ingresos)} · Gastos {soles(fila.gastos)}
        </div>
      )}
    </div>
  )
}

export default function CurvaTendencia() {
  const [granularidad, setGranularidad] = useState('mes')
  const [metrica, setMetrica] = useState('ingresos')
  const [puntos, setPuntos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let activo = true
    setCargando(true)
    setError(null)
    api
      .serie(granularidad)
      .then((r) => activo && setPuntos(r?.puntos ?? []))
      .catch((e) => activo && setError(e.message))
      .finally(() => activo && setCargando(false))
    return () => {
      activo = false
    }
  }, [granularidad])

  const ventana = VENTANA[granularidad]
  const etiquetaMetrica = METRICAS.find((m) => m.valor === metrica)?.etiqueta ?? ''

  const suficientes = hayDatosSuficientes(puntos.length, ventana.periodos)

  const datos = useMemo(() => {
    const base = puntos.map((p) => ({ ...p, valor: Number(p[metrica]) }))
    return suficientes ? mediaMovil(base, 'valor', ventana.periodos) : base
  }, [puntos, metrica, ventana, suficientes])

  // El balance y el acumulado cruzan el cero; los ingresos no.
  const puedeSerNegativo = metrica !== 'ingresos'
  const hayMedia = suficientes && datos.some((d) => d.media != null)

  if (cargando && !puntos.length) {
    return (
      <div className="grid h-[300px] place-items-center">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return <p className="py-12 text-center text-sm text-red-300">{error}</p>
  }

  if (datos.length < 2) {
    return (
      <p className="py-12 text-center text-sm text-muted-foreground">
        Necesitas al menos 2 periodos de datos para ver la tendencia.
      </p>
    )
  }

  return (
    <div>
      {/* Controles en una sola fila encima del gráfico */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Segmentado
          opciones={GRANULARIDADES}
          valor={granularidad}
          onChange={setGranularidad}
          aria="Granularidad"
        />
        <Segmentado
          opciones={METRICAS}
          valor={metrica}
          onChange={setMetrica}
          aria="Métrica"
        />
        <div className="ml-auto flex items-center gap-4">
          <Leyenda color={COLORES.serie} texto={etiquetaMetrica} />
          {hayMedia && (
            <Leyenda color={COLORES.media} texto={ventana.etiqueta} punteada />
          )}
        </div>
      </div>

      {hayMedia ? (
        <p className="mb-3 text-xs text-muted-foreground">
          La línea punteada es el promedio de {ventana.corta} hacia atrás: suaviza los
          picos de un solo día para que se vea la tendencia de fondo. Empieza recién
          en el punto {ventana.periodos}, porque antes no hay {ventana.corta} que
          promediar.
        </p>
      ) : (
        <p className="mb-3 text-xs text-muted-foreground">
          El promedio de {ventana.corta} no se muestra: con {puntos.length}{' '}
          {puntos.length === 1 ? 'periodo' : 'periodos'} arrancaría a mitad del
          gráfico y no diría nada. Prueba con una granularidad más fina o sube más
          meses.
        </p>
      )}

      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={datos} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="degradadoSerie" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={COLORES.serie} stopOpacity={0.3} />
              <stop offset="100%" stopColor={COLORES.serie} stopOpacity={0} />
            </linearGradient>
          </defs>

          <CartesianGrid stroke={COLORES.grilla} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="etiqueta"
            {...ejeComun}
            minTickGap={28}
            interval="preserveStartEnd"
          />
          <YAxis tickFormatter={solesCorto} width={68} {...ejeComun} />

          {puedeSerNegativo && (
            <ReferenceLine y={0} stroke={COLORES.eje} strokeWidth={1} />
          )}

          <Tooltip
            content={
              <TooltipCurva etiquetaMetrica={etiquetaMetrica} ventana={ventana} />
            }
            cursor={{ stroke: COLORES.serie, strokeWidth: 1, strokeDasharray: '4 4' }}
          />

          <Area
            type="monotone"
            dataKey="valor"
            name={etiquetaMetrica}
            stroke={COLORES.serie}
            strokeWidth={2}
            fill="url(#degradadoSerie)"
            dot={false}
            activeDot={{
              r: 5,
              fill: COLORES.serie,
              stroke: COLORES.superficie,
              strokeWidth: 2,
            }}
            isAnimationActive={false}
          />

          {hayMedia && (
            <Line
              type="monotone"
              dataKey="media"
              name={ventana.etiqueta}
              stroke={COLORES.media}
              strokeWidth={2}
              strokeDasharray="5 4"
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          )}

          {datos.length > 12 && (
            <Brush
              dataKey="etiqueta"
              height={22}
              travellerWidth={8}
              stroke={COLORES.eje}
              fill="rgba(255,255,255,0.03)"
              tickFormatter={() => ''}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
