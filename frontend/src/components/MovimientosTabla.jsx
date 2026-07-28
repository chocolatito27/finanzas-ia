/**
 * Tabla de movimientos con filtros por categoría y mes.
 *
 * También es la "vista de tabla" que acompaña a los gráficos: los mismos datos en
 * texto, para quien no puede leer los colores.
 *
 * El usuario puede corregir la categoría de un movimiento mal clasificado — es la
 * salida para los que quedaron en DESCONOCIDO.
 */

import { useEffect, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { api } from '@/lib/api'
import {
  LISTA_CATEGORIAS,
  etiquetaMes,
  fechaPeru,
  infoCategoria,
  soles,
} from '@/lib/utils'

const TODAS = '__todas__'

function EtiquetaCategoria({ categoria }) {
  const info = infoCategoria(categoria)
  return (
    <Badge
      variant="outline"
      className="gap-1.5 font-normal border-white/12 bg-white/4 whitespace-nowrap"
    >
      <span
        className="inline-block size-2 rounded-full shrink-0"
        style={{ background: info.color }}
      />
      {info.etiqueta}
    </Badge>
  )
}

export default function MovimientosTabla({ meses = [], onCambio }) {
  const [movimientos, setMovimientos] = useState([])
  const [categoria, setCategoria] = useState(TODAS)
  const [mes, setMes] = useState(TODAS)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [editando, setEditando] = useState(null)

  useEffect(() => {
    let activo = true
    setCargando(true)
    setError(null)
    api
      .movimientos({
        categoria: categoria === TODAS ? undefined : categoria,
        mes: mes === TODAS ? undefined : mes,
      })
      .then((datos) => activo && setMovimientos(datos ?? []))
      .catch((e) => activo && setError(e.message))
      .finally(() => activo && setCargando(false))
    return () => {
      activo = false
    }
  }, [categoria, mes])

  async function corregir(id, nuevaCategoria) {
    setEditando(id)
    try {
      await api.cambiarCategoria(id, nuevaCategoria)
      setMovimientos((previos) =>
        previos.map((m) => (m.id === id ? { ...m, categoria: nuevaCategoria } : m)),
      )
      onCambio?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setEditando(null)
    }
  }

  return (
    <div>
      {/* Filtros: una sola fila encima de la tabla */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <Select value={categoria} onValueChange={setCategoria}>
          <SelectTrigger className="w-[210px]">
            {/* Base UI muestra el valor crudo si no se le da cómo renderizarlo */}
            <SelectValue>
              {(valor) =>
                valor === TODAS
                  ? 'Todas las categorías'
                  : infoCategoria(valor).etiqueta
              }
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={TODAS}>Todas las categorías</SelectItem>
            {LISTA_CATEGORIAS.map((clave) => (
              <SelectItem key={clave} value={clave}>
                {infoCategoria(clave).etiqueta}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={mes} onValueChange={setMes}>
          <SelectTrigger className="w-[170px]">
            <SelectValue>
              {(valor) => (valor === TODAS ? 'Todos los meses' : etiquetaMes(valor))}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={TODAS}>Todos los meses</SelectItem>
            {meses.map((m) => (
              <SelectItem key={m} value={m}>
                {etiquetaMes(m)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <span className="text-sm text-muted-foreground ml-auto tabular">
          {cargando ? 'Cargando…' : `${movimientos.length} movimientos`}
        </span>
      </div>

      {error && (
        <p className="mb-4 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-red-300">
          {error}
        </p>
      )}

      <div className="overflow-x-auto rounded-xl border border-white/10">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent border-white/10">
              <TableHead className="w-[104px]">Fecha</TableHead>
              <TableHead>Descripción</TableHead>
              <TableHead className="w-[210px]">Categoría</TableHead>
              <TableHead className="w-[130px] text-right">Monto</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {!cargando && movimientos.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground py-10">
                  No hay movimientos con estos filtros.
                </TableCell>
              </TableRow>
            )}

            {movimientos.map((m) => {
              const esIngreso = Number(m.monto) > 0
              return (
                <TableRow key={m.id} className="border-white/8">
                  <TableCell className="font-mono text-sm text-muted-foreground tabular">
                    {fechaPeru(m.fecha)}
                  </TableCell>
                  <TableCell>
                    <div className="text-foreground">
                      {m.descripcion_limpia || m.descripcion_original}
                    </div>
                    {m.descripcion_limpia &&
                      m.descripcion_original &&
                      m.descripcion_limpia !== m.descripcion_original && (
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {m.descripcion_original}
                        </div>
                      )}
                  </TableCell>
                  <TableCell>
                    <Select
                      value={m.categoria}
                      onValueChange={(valor) => corregir(m.id, valor)}
                      disabled={editando === m.id}
                    >
                      <SelectTrigger className="h-8 border-0 bg-transparent px-0 shadow-none hover:bg-white/5 focus-visible:ring-1">
                        <EtiquetaCategoria categoria={m.categoria} />
                      </SelectTrigger>
                      <SelectContent>
                        {LISTA_CATEGORIAS.map((clave) => (
                          <SelectItem key={clave} value={clave}>
                            {infoCategoria(clave).etiqueta}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell
                    className="text-right font-mono font-medium tabular whitespace-nowrap"
                    style={{ color: esIngreso ? '#10b981' : '#ef4444' }}
                  >
                    {esIngreso ? '+' : ''}
                    {soles(m.monto)}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
