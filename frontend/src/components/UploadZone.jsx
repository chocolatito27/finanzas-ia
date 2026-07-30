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
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import { cn, fechaPeru } from '@/lib/utils'

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

export default function UploadZone({ onProcesado, onClaveGuardada }) {
  const inputRef = useRef(null)
  const listaRef = useRef(null)
  const [seleccionados, setSeleccionados] = useState([])
  const [subiendo, setSubiendo] = useState(false)
  const [arrastrando, setArrastrando] = useState(false)
  const [resultados, setResultados] = useState(null)
  const [error, setError] = useState(null)
  const [clavePdf, setClavePdf] = useState('')
  const [guardandoClave, setGuardandoClave] = useState(false)
  const resultadosRef = useRef(null)

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

      // Solo se quitan de la lista los que SÍ se procesaron. Antes se vaciaba
      // entera: la lista y el botón desaparecían de golpe, el contenido saltaba
      // hacia arriba —parecía que la página se había recargado— y encima había
      // que volver a elegir el archivo para reintentar. En celular, donde el
      // resultado queda fuera de pantalla, eso se leía como "no pasó nada".
      const fallados = new Set(
        respuesta.resultados.filter((r) => !r.ok).map((r) => r.nombre_archivo),
      )
      setSeleccionados((previos) => previos.filter((a) => fallados.has(a.name)))

      if (respuesta.total_movimientos > 0) onProcesado?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setSubiendo(false)
      // El resultado —sobre todo cuando es un error— queda debajo del pliegue en
      // celular. Sin esto, el usuario ve que el spinner se apaga y concluye que
      // "no pasó nada", cuando en realidad hay un mensaje explicando qué falló.
      requestAnimationFrame(() => {
        resultadosRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      })
    }
  }

  const hayClaveMala = resultados?.some((r) => r.codigo_error === 'PDF_PROTEGIDO')

  /**
   * Guarda la clave y reintenta la subida sin que el usuario tenga que volver a
   * elegir el archivo.
   *
   * Antes esto eran cinco pasos: leer el error, encontrar el enlace de la clave,
   * abrir el formulario, guardarla y volver a seleccionar el archivo (que además
   * ya se había perdido). En celular era motivo suficiente para abandonar.
   */
  async function guardarClaveYReintentar(evento) {
    evento.preventDefault()
    const limpia = clavePdf.trim()
    if (!limpia) return

    setGuardandoClave(true)
    setError(null)
    try {
      await api.actualizarClavePdf(limpia)
      setClavePdf('')
      onClaveGuardada?.()
      // Los archivos que fallaron siguen en la lista, así que se reintenta solo
      if (seleccionados.length) await procesar()
    } catch (e) {
      setError(e.message)
    } finally {
      setGuardandoClave(false)
    }
  }

  return (
    <div>
      {/* --- Zona de subida ---
           Toda la zona es un botón: en celular no se puede arrastrar, y obligar a
           acertarle a un botón chico dentro de un recuadro grande es una molestia
           innecesaria. En pantalla ancha además acepta arrastrar. */}
      {/* Es un div y no un <label>: con el input encima a tamaño completo, un
          label apuntando al mismo input dispara el evento dos veces en algunos
          navegadores. */}
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
          // relative: el input se estira encima de toda la zona (ver abajo)
          'relative block w-full rounded-xl border border-dashed px-6 py-9 text-center transition-colors',
          subiendo
            ? 'pointer-events-none opacity-60'
            : 'cursor-pointer active:bg-white/4',
          arrastrando
            ? 'border-primary bg-primary/8'
            : 'border-white/15 hover:border-white/25',
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

        {/* El input se estira transparente sobre TODA la zona, en vez de estar
            escondido en una esquina.

            Historia de este bloque, porque importa: primero estaba con la clase
            `hidden` (display:none) y se abría con un .click() por JavaScript —
            varios navegadores de celular ignoran eso, y el usuario elegía su
            archivo sin que pasara nada. Después pasó a `sr-only` dentro de un
            <label>, que es el patrón recomendado, y en Chrome de Android tampoco
            funcionó.

            Esto es lo más compatible que existe: el dedo del usuario toca el
            input de verdad, a tamaño completo. No hay label que reenvíe el
            evento, ni .click() sintético, ni un control de 1px que el navegador
            pueda considerar no interactuable.

            Sin `accept` a propósito: en Android, filtrar por tipo hace que varios
            gestores de archivos muestren los PDF en gris y no se puedan elegir.
            El formato real se valida por el contenido en el backend. */}
        <input
          id="entrada-archivos"
          ref={inputRef}
          type="file"
          multiple
          disabled={subiendo}
          aria-label="Seleccionar estados de cuenta"
          className="absolute inset-0 size-full cursor-pointer opacity-0"
          onClick={(e) => {
            // Limpiar acá permite volver a elegir el mismo archivo. Se hace antes
            // de que se abra el selector, no después de leer los archivos, porque
            // eso último invalida las referencias en Safari de iOS.
            e.currentTarget.value = ''
          }}
          onChange={(e) => agregar(e.target.files)}
        />
      </div>

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

      {/* Ancla para desplazar la vista hasta el resultado en celular */}
      <div ref={resultadosRef} />

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

          {/* El formulario aparece acá mismo, pegado al error que lo motiva, y
              al guardar reintenta solo. Antes era un enlace que abría otro
              formulario en otra parte de la página, y para entonces el archivo
              ya se había perdido. */}
          {hayClaveMala && (
            <form
              onSubmit={guardarClaveYReintentar}
              className="rounded-xl border border-white/10 bg-white/3 p-4"
            >
              <div className="flex items-center gap-2">
                <KeyRound className="size-4 text-muted-foreground" />
                <p className="text-sm font-medium text-foreground">
                  Escribe la clave de tus PDFs del banco
                </p>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Normalmente es el DNI del titular de la cuenta, sin guiones ni
                espacios.
              </p>
              <Input
                type="password"
                inputMode="numeric"
                autoComplete="off"
                maxLength={64}
                value={clavePdf}
                onChange={(e) => setClavePdf(e.target.value)}
                placeholder="Ej. 12345678"
                className="mt-3"
              />
              <Button
                type="submit"
                className="mt-3 w-full"
                disabled={guardandoClave || subiendo || !clavePdf.trim()}
              >
                {(guardandoClave || subiendo) && (
                  <Loader2 className="size-4 animate-spin" />
                )}
                Guardar clave y reintentar
              </Button>
            </form>
          )}
        </div>
      )}
    </div>
  )
}
