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

// Los tipos MIME van junto a las extensiones porque en celular el selector de
// archivos suele filtrar por MIME y no por extensión.
const ACEPTADOS =
  '.pdf,.xlsx,.xlsm,.csv,application/pdf,text/csv,' +
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

const EXTENSIONES = ['.pdf', '.xlsx', '.xlsm', '.csv']
const MIMES = ['application/pdf', 'text/csv', 'spreadsheetml', 'excel']
const MAX_ARCHIVOS = 12
const MAX_MB = 15

function iconoArchivo(nombre) {
  return nombre.toLowerCase().endsWith('.pdf') ? FileText : FileSpreadsheet
}

/**
 * Decide si un archivo se acepta en la lista.
 *
 * Es deliberadamente permisivo. Antes se filtraba solo por la extensión del
 * nombre y **se descartaba en silencio** todo lo demás: en celular, donde el
 * selector de archivos (Google Drive, Archivos, adjuntos de WhatsApp) entrega
 * nombres sin extensión o genéricos tipo "Documento", el usuario elegía su PDF
 * y no pasaba absolutamente nada, sin mensaje alguno.
 *
 * Ahora, si el nombre no dice nada útil, se deja pasar y decide el backend, que
 * mira los bytes del archivo. Es mejor mandar algo dudoso y recibir un error
 * claro que rechazarlo sin explicación.
 */
function revisar(archivo) {
  if (archivo.size === 0) {
    return { ok: false, motivo: 'está vacío' }
  }
  if (archivo.size > MAX_MB * 1024 * 1024) {
    return { ok: false, motivo: `pesa más de ${MAX_MB} MB` }
  }

  const nombre = (archivo.name || '').toLowerCase()
  const tipo = (archivo.type || '').toLowerCase()

  if (EXTENSIONES.some((e) => nombre.endsWith(e))) return { ok: true }
  if (MIMES.some((m) => tipo.includes(m))) return { ok: true }

  // Formatos que claramente no sirven: se atajan acá con un mensaje útil
  if (tipo.startsWith('image/')) {
    return {
      ok: false,
      motivo: 'es una imagen. Necesitamos el PDF que descargas del banco, no una foto',
    }
  }
  if (nombre.endsWith('.xls')) {
    return {
      ok: false,
      motivo: 'es un Excel antiguo (.xls). Ábrelo y guárdalo como .xlsx',
    }
  }

  // Sin extensión ni tipo reconocible: que decida el backend por el contenido
  return { ok: true }
}

export default function UploadZone({ onProcesado, onPedirClave }) {
  const inputRef = useRef(null)
  const listaRef = useRef(null)
  const [seleccionados, setSeleccionados] = useState([])
  const [subiendo, setSubiendo] = useState(false)
  const [arrastrando, setArrastrando] = useState(false)
  const [resultados, setResultados] = useState(null)
  const [error, setError] = useState(null)

  function abrirSelector() {
    if (!inputRef.current) return
    // Se limpia ANTES de abrir el selector, no después de leer los archivos.
    // Hacerlo en el onChange (justo tras copiar la FileList) invalida las
    // referencias a los archivos en Safari de iOS, y la subida se queda a medias
    // sin ningún error. Limpiar acá logra lo mismo —permitir volver a elegir el
    // mismo archivo— sin ese riesgo.
    inputRef.current.value = ''
    inputRef.current.click()
  }

  function agregar(lista) {
    const archivos = Array.from(lista || [])
    setResultados(null)
    setError(null)

    if (archivos.length === 0) {
      // Pasa en celular cuando el selector devuelve vacío: el usuario cree que
      // eligió algo y no ocurre nada. Mejor decirlo que dejarlo en silencio.
      setError(
        'No se recibió ningún archivo. Si lo elegiste desde Drive o WhatsApp, ' +
          'descárgalo primero al teléfono y vuelve a intentarlo desde Archivos o Descargas.',
      )
      return
    }

    const aceptados = []
    const rechazados = []
    for (const archivo of archivos) {
      const veredicto = revisar(archivo)
      if (veredicto.ok) aceptados.push(archivo)
      else rechazados.push(`${archivo.name || 'el archivo'} ${veredicto.motivo}`)
    }

    // Nunca descartar en silencio: si algo no entra, hay que decir por qué.
    if (rechazados.length) {
      setError(
        rechazados.length === 1
          ? `No se puede subir: ${rechazados[0]}.`
          : `No se pudieron subir ${rechazados.length} archivos: ${rechazados.join('; ')}.`,
      )
    }

    if (aceptados.length) {
      setSeleccionados((previos) => {
        const total = [...previos, ...aceptados]
        if (total.length > MAX_ARCHIVOS) {
          setError(`Máximo ${MAX_ARCHIVOS} archivos por vez.`)
        }
        return total.slice(0, MAX_ARCHIVOS)
      })

      // En celular la lista y el botón "Procesar" quedan debajo del pliegue: el
      // archivo sí se agregó, pero sin ver el botón parece que no pasó nada.
      requestAnimationFrame(() => {
        listaRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      })
    }
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
      {/* --- Zona de subida ---
           Toda la zona es un botón: en celular no se puede arrastrar, y obligar a
           acertarle a un botón chico dentro de un recuadro grande es una molestia
           innecesaria. En pantalla ancha además acepta arrastrar. */}
      <button
        type="button"
        onClick={abrirSelector}
        disabled={subiendo}
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
          'w-full rounded-xl border border-dashed px-6 py-9 text-center transition-colors',
          'disabled:opacity-60 disabled:cursor-not-allowed',
          arrastrando
            ? 'border-primary bg-primary/8'
            : 'border-white/15 hover:border-white/25 active:bg-white/4',
        )}
      >
        <UploadCloud className="mx-auto size-9 text-muted-foreground" />
        <span className="mt-3 block text-foreground font-medium">
          {/* El texto cambia según el tamaño: en celular no hay nada que arrastrar */}
          <span className="sm:hidden">Toca para elegir tus estados de cuenta</span>
          <span className="hidden sm:inline">
            Arrastra tus estados de cuenta aquí o toca para elegirlos
          </span>
        </span>
        <span className="mt-1 block text-sm text-muted-foreground">
          PDF o Excel · hasta {MAX_ARCHIVOS} archivos · {MAX_MB} MB cada uno
        </span>
        <span className="mt-4 inline-block rounded-lg bg-secondary px-3 py-2 text-sm font-medium text-secondary-foreground">
          Seleccionar archivos
        </span>
      </button>

      {/* Fuera del <button>: un input dentro de un botón es HTML inválido y el
          clic se dispararía dos veces. */}
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACEPTADOS}
        className="hidden"
        onChange={(e) => agregar(e.target.files)}
      />

      {/* --- Lista de seleccionados --- */}
      {seleccionados.length > 0 && (
        <div ref={listaRef} className="mt-4 space-y-2">
          <p className="text-sm text-foreground">
            {seleccionados.length}{' '}
            {seleccionados.length === 1 ? 'archivo listo' : 'archivos listos'} para
            procesar:
          </p>
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
                Leyendo y categorizando con IA…
              </>
            ) : (
              `Procesar ${seleccionados.length} archivo${seleccionados.length === 1 ? '' : 's'}`
            )}
          </Button>

          {subiendo && (
            <p className="text-center text-xs text-muted-foreground">
              Puede tardar entre 30 s y 2 minutos. No cierres esta pantalla.
            </p>
          )}
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
