/**
 * Zona de subida de estados de cuenta (arrastrar o seleccionar, varios a la vez).
 *
 * El procesamiento tarda 30–60 s, así que muestra un estado de carga explícito con
 * lo que está pasando. Al terminar informa archivo por archivo: los errores comunes
 * (PDF con clave equivocada, archivo repetido, formato no reconocido) tienen un
 * mensaje propio, no un "error" genérico.
 */

import { useRef, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  FileSpreadsheet,
  FileText,
  KeyRound,
  Loader2,
  UploadCloud,
  X,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { cn, fechaPeru } from '@/lib/utils'

const EXTENSIONES = '.pdf,.xlsx,.xlsm,.xls,.csv'
const MAX_ARCHIVOS = 12

function iconoArchivo(nombre) {
  return nombre.toLowerCase().endsWith('.pdf') ? FileText : FileSpreadsheet
}

export default function UploadZone({ onProcesado, onPedirClave }) {
  const inputRef = useRef(null)
  const [seleccionados, setSeleccionados] = useState([])
  const [subiendo, setSubiendo] = useState(false)
  const [arrastrando, setArrastrando] = useState(false)
  const [resultados, setResultados] = useState(null)
  const [error, setError] = useState(null)

  function agregar(lista) {
    const nuevos = Array.from(lista).filter((archivo) =>
      EXTENSIONES.split(',').some((ext) => archivo.name.toLowerCase().endsWith(ext)),
    )
    setSeleccionados((previos) => [...previos, ...nuevos].slice(0, MAX_ARCHIVOS))
    setResultados(null)
    setError(null)
  }

  function quitar(indice) {
    setSeleccionados((previos) => previos.filter((_, i) => i !== indice))
  }

  async function procesar() {
    if (!seleccionados.length) return
    setSubiendo(true)
    setError(null)
    setResultados(null)
    try {
      const respuesta = await api.subirArchivos(seleccionados)
      setResultados(respuesta.resultados)
      setSeleccionados([])
      if (inputRef.current) inputRef.current.value = ''
      if (respuesta.total_movimientos > 0) onProcesado?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setSubiendo(false)
    }
  }

  const hayClaveMala = resultados?.some((r) => r.codigo_error === 'PDF_PROTEGIDO')

  return (
    <div>
      {/* --- Zona de drop --- */}
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setArrastrando(true)
        }}
        onDragLeave={() => setArrastrando(false)}
        onDrop={(e) => {
          e.preventDefault()
          setArrastrando(false)
          agregar(e.dataTransfer.files)
        }}
        className={cn(
          'rounded-xl border border-dashed px-6 py-10 text-center transition-colors',
          arrastrando
            ? 'border-primary bg-primary/8'
            : 'border-white/15 hover:border-white/25',
        )}
      >
        <UploadCloud className="mx-auto size-9 text-muted-foreground" />
        <p className="mt-3 text-foreground font-medium">
          Arrastra tus estados de cuenta aquí
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          PDF o Excel · hasta {MAX_ARCHIVOS} archivos · 15 MB cada uno
        </p>
        <Button
          type="button"
          variant="secondary"
          className="mt-4"
          onClick={() => inputRef.current?.click()}
          disabled={subiendo}
        >
          Seleccionar archivos
        </Button>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={EXTENSIONES}
          className="hidden"
          onChange={(e) => agregar(e.target.files)}
        />
      </div>

      {/* --- Lista de seleccionados --- */}
      {seleccionados.length > 0 && (
        <div className="mt-4 space-y-2">
          {seleccionados.map((archivo, indice) => {
            const Icono = iconoArchivo(archivo.name)
            return (
              <div
                key={`${archivo.name}-${indice}`}
                className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/3 px-3.5 py-2.5"
              >
                <Icono className="size-4 shrink-0 text-muted-foreground" />
                <span className="truncate text-sm text-foreground">{archivo.name}</span>
                <span className="ml-auto shrink-0 text-xs text-muted-foreground tabular">
                  {(archivo.size / 1024 / 1024).toFixed(1)} MB
                </span>
                <button
                  type="button"
                  onClick={() => quitar(indice)}
                  disabled={subiendo}
                  className="shrink-0 rounded p-1 text-muted-foreground hover:text-foreground hover:bg-white/8"
                  aria-label={`Quitar ${archivo.name}`}
                >
                  <X className="size-3.5" />
                </button>
              </div>
            )
          })}

          <Button onClick={procesar} disabled={subiendo} className="w-full mt-2">
            {subiendo ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Leyendo y categorizando con IA… (30–60 s)
              </>
            ) : (
              `Procesar ${seleccionados.length} archivo${seleccionados.length === 1 ? '' : 's'}`
            )}
          </Button>
        </div>
      )}

      {error && (
        <p className="mt-4 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-red-300">
          {error}
        </p>
      )}

      {/* --- Resultado archivo por archivo --- */}
      {resultados && (
        <div className="mt-5 space-y-2">
          {resultados.map((r, indice) => (
            <div
              key={`${r.nombre_archivo}-${indice}`}
              className={cn(
                'flex gap-3 rounded-xl border px-3.5 py-3 text-sm',
                r.ok
                  ? 'border-emerald-500/25 bg-emerald-500/8'
                  : 'border-amber-500/25 bg-amber-500/8',
              )}
            >
              {r.ok ? (
                <CheckCircle2 className="size-4 shrink-0 text-emerald-400 mt-0.5" />
              ) : (
                <AlertCircle className="size-4 shrink-0 text-amber-400 mt-0.5" />
              )}
              <div className="min-w-0">
                <p className="truncate font-medium text-foreground">{r.nombre_archivo}</p>
                {r.ok ? (
                  <p className="text-muted-foreground mt-0.5">
                    {r.movimientos_insertados} movimientos
                    {r.banco_detectado ? ` · ${r.banco_detectado}` : ''}
                    {r.mes_inicio
                      ? ` · ${fechaPeru(r.mes_inicio)} a ${fechaPeru(r.mes_fin)}`
                      : ''}
                  </p>
                ) : (
                  <p className="text-amber-200/90 mt-0.5">{r.error}</p>
                )}
              </div>
            </div>
          ))}

          {hayClaveMala && onPedirClave && (
            <Button variant="secondary" className="w-full" onClick={onPedirClave}>
              <KeyRound className="size-4" />
              Actualizar la clave de mis PDFs
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
