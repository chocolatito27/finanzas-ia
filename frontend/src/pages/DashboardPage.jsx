/**
 * Dashboard principal.
 *
 * Orden de lectura: primero los tres números del mes (lo que la persona vino a ver),
 * después el detalle mes a mes, la tendencia, la proyección y por último la tabla.
 */

import { useCallback, useEffect, useState } from 'react'
import {
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  KeyRound,
  Loader2,
  Scale,
} from 'lucide-react'

import Layout from '@/components/Layout'
import MovimientosTabla from '@/components/MovimientosTabla'
import UploadZone from '@/components/UploadZone'
import CurvaTendencia from '@/components/graficos/CurvaTendencia'
import GastosPorCategoria from '@/components/graficos/GastosPorCategoria'
import GraficoBarras from '@/components/graficos/GraficoBarras'
import ProyeccionAnual from '@/components/graficos/ProyeccionAnual'
import { COLORES_KPI } from '@/components/graficos/tema'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { etiquetaMes, soles } from '@/lib/utils'

function TarjetaKpi({ titulo, valor, Icono, color, nota }) {
  return (
    <Card className="border-white/10">
      <CardContent className="pt-1">
        <div className="flex items-center gap-2">
          <Icono className="size-4" style={{ color }} />
          <p className="text-sm text-muted-foreground">{titulo}</p>
        </div>
        <p
          className="mt-2 font-mono text-3xl font-bold tabular leading-none"
          style={{ color }}
        >
          {soles(valor)}
        </p>
        {nota && <p className="mt-2 text-xs text-muted-foreground">{nota}</p>}
      </CardContent>
    </Card>
  )
}

function FormularioClave({ onListo }) {
  const [clave, setClave] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState(null)
  const [guardada, setGuardada] = useState(false)

  async function guardar(evento) {
    evento.preventDefault()
    const limpia = clave.trim()
    if (!limpia) {
      setError('Escribe la clave antes de guardar.')
      return
    }
    setGuardando(true)
    setError(null)
    try {
      await api.actualizarClavePdf(limpia)
      setClave('')
      setGuardada(true)
      onListo?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form onSubmit={guardar} className="mt-4 space-y-3">
      <div className="space-y-2">
        <Label htmlFor="clave-nueva">Clave de tus PDFs del banco</Label>
        <Input
          id="clave-nueva"
          type="password"
          autoComplete="off"
          maxLength={64}
          value={clave}
          onChange={(e) => {
            setClave(e.target.value)
            setError(null)
            setGuardada(false)
          }}
          placeholder="Normalmente tu DNI"
        />
        <p className="text-xs text-muted-foreground">
          Se guarda cifrada y solo se usa para abrir tus PDFs protegidos.
        </p>
      </div>

      {error && (
        <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-red-300">
          {error}
        </p>
      )}
      {guardada && (
        <p className="flex items-center gap-2 text-sm text-emerald-300">
          <CheckCircle2 className="size-4" />
          Clave guardada. Vuelve a subir tu archivo.
        </p>
      )}

      <Button type="submit" size="sm" disabled={guardando || !clave.trim()}>
        {guardando && <Loader2 className="size-4 animate-spin" />}
        Guardar clave
      </Button>
    </form>
  )
}

export default function DashboardPage() {
  const { perfil, recargarPerfil } = useAuth()
  const tieneClave = !!perfil?.tiene_clave_pdf
  const [datos, setDatos] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [version, setVersion] = useState(0)
  const [mostrarClave, setMostrarClave] = useState(false)

  const cargar = useCallback(() => {
    setCargando(true)
    setError(null)
    api
      .dashboard()
      .then(setDatos)
      .catch((e) => setError(e.message))
      .finally(() => setCargando(false))
  }, [])

  useEffect(cargar, [cargar, version])

  const refrescar = () => setVersion((v) => v + 1)

  if (cargando && !datos) {
    return (
      <Layout>
        <div className="grid place-items-center py-32">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      </Layout>
    )
  }

  const mesActual = datos?.mes_actual
  const meses = (datos?.resumen_mensual ?? []).map((m) => m.mes).reverse()
  const sinDatos = (datos?.total_movimientos ?? 0) === 0

  return (
    <Layout>
      {error && (
        <div className="mb-6 flex gap-2.5 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3">
          <AlertCircle className="size-4 shrink-0 text-red-400 mt-0.5" />
          <p className="text-sm text-red-300">{error}</p>
        </div>
      )}

      {/* --- KPIs del mes --- */}
      <div className="mb-6 flex flex-wrap items-baseline gap-x-3">
        <h1 className="text-2xl font-bold text-foreground">Resumen</h1>
        {mesActual && !sinDatos && (
          <span className="text-muted-foreground">{etiquetaMes(mesActual.mes)}</span>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <TarjetaKpi
          titulo="Ingresos del mes"
          valor={mesActual?.ingresos ?? 0}
          Icono={ArrowUpRight}
          color={COLORES_KPI.ingreso}
        />
        <TarjetaKpi
          titulo="Gastos del mes"
          valor={mesActual?.gastos ?? 0}
          Icono={ArrowDownRight}
          color={COLORES_KPI.gasto}
        />
        <TarjetaKpi
          titulo="Balance del mes"
          valor={mesActual?.balance ?? 0}
          Icono={Scale}
          color={Number(mesActual?.balance ?? 0) >= 0 ? COLORES_KPI.ingreso : COLORES_KPI.gasto}
          nota="Sin contar transferencias entre tus cuentas"
        />
      </div>

      {/* --- Subida --- */}
      <Card className="mt-6 border-white/10">
        <CardHeader>
          <CardTitle>Subir estados de cuenta</CardTitle>
          <CardDescription>
            PDF o Excel de tu banco. Puedes subir varios meses a la vez.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <UploadZone onProcesado={refrescar} onClaveGuardada={recargarPerfil} />

          {/* Siempre accesible: antes solo aparecía después de que fallara una
              subida, y era el único camino para corregir una clave equivocada. */}
          <button
            type="button"
            onClick={() => setMostrarClave((v) => !v)}
            className="mt-4 flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <KeyRound className="size-4" />
            {tieneClave
              ? 'Cambiar la clave de mis PDFs'
              : 'Mis PDFs tienen clave: configurarla'}
          </button>

          {mostrarClave && (
            <div className="mt-3 rounded-xl border border-white/10 bg-white/3 p-4">
              <FormularioClave
                onListo={() => {
                  setMostrarClave(false)
                  recargarPerfil()
                }}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {sinDatos ? (
        <Card className="mt-6 border-white/10">
          <CardContent className="py-14 text-center">
            <p className="text-foreground font-medium">Todavía no hay movimientos</p>
            <p className="mt-1.5 text-sm text-muted-foreground">
              Sube tu primer estado de cuenta arriba y tu dashboard se arma solo.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* --- Gráficos --- */}
          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <Card className="border-white/10">
              <CardHeader>
                <CardTitle>Ingresos vs gastos por mes</CardTitle>
                <CardDescription>En Soles, sin transferencias internas</CardDescription>
              </CardHeader>
              <CardContent>
                <GraficoBarras datos={datos.resumen_mensual} />
              </CardContent>
            </Card>

            <Card className="border-white/10">
              <CardHeader>
                <CardTitle>Tendencia</CardTitle>
                <CardDescription>
                  Elige si lo quieres ver por día, semana o mes
                </CardDescription>
              </CardHeader>
              <CardContent>
                <CurvaTendencia key={version} />
              </CardContent>
            </Card>
          </div>

          <Card className="mt-4 border-white/10">
            <CardHeader>
              <CardTitle>Proyección de cierre de año</CardTitle>
              <CardDescription>
                Extrapolación lineal: promedio mensual × 12
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ProyeccionAnual proyeccion={datos.proyeccion} />
            </CardContent>
          </Card>

          <Card className="mt-4 border-white/10">
            <CardHeader>
              <CardTitle>Totales por categoría</CardTitle>
              <CardDescription>
                {datos.movimientos_desconocidos > 0
                  ? `${datos.movimientos_desconocidos} movimientos sin clasificar: corrígelos en la tabla de abajo`
                  : 'Todos los movimientos están clasificados'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <GastosPorCategoria datos={datos.por_categoria} />
            </CardContent>
          </Card>

          {/* --- Tabla --- */}
          <Card className="mt-4 border-white/10">
            <CardHeader>
              <CardTitle>Movimientos</CardTitle>
              <CardDescription>
                {datos.total_movimientos} en total. Haz clic en una categoría para
                corregirla.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <MovimientosTabla meses={meses} onCambio={refrescar} />
            </CardContent>
          </Card>
        </>
      )}
    </Layout>
  )
}
