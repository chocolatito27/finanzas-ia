/**
 * Proyección de cierre de año.
 *
 * El dato principal es un número, no un gráfico: va como cifra grande. Debajo, una
 * barra apilada muestra qué parte de la proyección ya está realizada y qué parte es
 * estimada, con la parte estimada en un tono más tenue para que no se lea como un
 * hecho.
 *
 * Con menos de 2 meses de datos la extrapolación no significa nada, así que en vez
 * del número se muestra un aviso.
 */

import { AlertTriangle, TrendingUp } from 'lucide-react'

import { soles } from '@/lib/utils'
import { COLORES } from './tema'

function BarraProgreso({ acumulado, proyectado, color }) {
  const porcentaje =
    proyectado > 0 ? Math.min(100, Math.round((acumulado / proyectado) * 100)) : 0
  return (
    <div className="mt-3">
      <div className="h-2 w-full rounded-full bg-white/8 overflow-hidden flex gap-0.5">
        <div
          className="h-full rounded-l-full"
          style={{ width: `${porcentaje}%`, background: color }}
        />
        <div
          className="h-full rounded-r-full"
          style={{ width: `${100 - porcentaje}%`, background: color, opacity: 0.28 }}
        />
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        <span className="text-foreground tabular font-mono">{porcentaje}%</span> ya
        registrado · el resto es estimado
      </p>
    </div>
  )
}

export default function ProyeccionAnual({ proyeccion }) {
  if (!proyeccion) return null

  const {
    anio,
    meses_con_datos: meses,
    confiable,
    ingresos_acumulados: ingresosAcum,
    gastos_acumulados: gastosAcum,
    ingresos_proyectados_cierre: ingresosCierre,
    gastos_proyectados_cierre: gastosCierre,
    balance_proyectado_cierre: balanceCierre,
    promedio_ingreso_mensual: promedioIngreso,
  } = proyeccion

  if (meses === 0) {
    return (
      <p className="text-sm text-muted-foreground py-8 text-center">
        Sube tus estados de cuenta para ver la proyección del año.
      </p>
    )
  }

  return (
    <div>
      {!confiable && (
        <div className="mb-5 flex gap-2.5 rounded-xl border border-amber-500/25 bg-amber-500/8 px-3.5 py-3">
          <AlertTriangle className="size-4 shrink-0 text-amber-400 mt-0.5" />
          <p className="text-sm text-amber-200/90">
            Solo hay <strong>{meses} mes</strong> de datos. La proyección es una
            extrapolación de ese único mes: súbelos de más meses para que sea confiable.
          </p>
        </div>
      )}

      <div className="grid gap-6 sm:grid-cols-2">
        <div>
          <p className="text-sm text-muted-foreground">
            Ingresos proyectados al cierre de {anio}
          </p>
          <p className="mt-1 font-mono text-3xl font-bold tabular text-foreground">
            {soles(ingresosCierre)}
          </p>
          <BarraProgreso
            acumulado={Number(ingresosAcum)}
            proyectado={Number(ingresosCierre)}
            color={COLORES.ingreso}
          />
        </div>

        <div>
          <p className="text-sm text-muted-foreground">
            Gastos proyectados al cierre de {anio}
          </p>
          <p className="mt-1 font-mono text-3xl font-bold tabular text-foreground">
            {soles(gastosCierre)}
          </p>
          <BarraProgreso
            acumulado={Number(gastosAcum)}
            proyectado={Number(gastosCierre)}
            color={COLORES.gasto}
          />
        </div>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-white/10 pt-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="size-4 text-acento-suave" />
          <span className="text-sm text-muted-foreground">Balance proyectado</span>
          <span
            className="font-mono font-semibold tabular"
            style={{
              color: Number(balanceCierre) >= 0 ? COLORES.ingreso : COLORES.gasto,
            }}
          >
            {soles(balanceCierre)}
          </span>
        </div>
        <div className="text-sm text-muted-foreground">
          Promedio mensual de ingresos:{' '}
          <span className="font-mono text-foreground tabular">{soles(promedioIngreso)}</span>
        </div>
        <div className="text-sm text-muted-foreground">
          Basado en <span className="text-foreground">{meses}</span>{' '}
          {meses === 1 ? 'mes' : 'meses'} con datos
        </div>
      </div>
    </div>
  )
}
