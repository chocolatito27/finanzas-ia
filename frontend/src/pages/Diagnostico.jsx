/**
 * Página de diagnóstico del selector de archivos.
 *
 * Existe porque no se pudo reproducir en escritorio un fallo que sí ocurre en
 * Chrome de Android: el usuario elige un archivo y no pasa absolutamente nada.
 * Después de tres intentos de arreglo a ciegas, esto deja de adivinar y mide.
 *
 * Prueba las tres formas de abrir un selector de archivos, registra cada evento
 * en pantalla y permite enviar el registro al servidor para poder leerlo.
 *
 * Ruta: /diagnostico
 */

import { useRef, useState } from 'react'
import { Send } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

function describir(archivo) {
  return {
    nombre: archivo.name,
    tamano: archivo.size,
    tipo: archivo.type || '(vacío)',
    modificado: archivo.lastModified,
  }
}

export default function Diagnostico() {
  const [registro, setRegistro] = useState([])
  const [enviando, setEnviando] = useState(false)
  const [enviado, setEnviado] = useState(null)
  const refOculto = useRef(null)

  const anotar = (evento, datos = {}) =>
    setRegistro((previo) => [
      ...previo,
      { t: new Date().toISOString().slice(11, 23), evento, ...datos },
    ])

  function alCambiar(etiqueta) {
    return (e) => {
      const archivos = Array.from(e.target.files || [])
      anotar(`change en ${etiqueta}`, {
        cantidad: archivos.length,
        archivos: archivos.map(describir),
      })
    }
  }

  async function enviar() {
    setEnviando(true)
    setEnviado(null)
    try {
      await api.enviarDiagnostico({
        agente: navigator.userAgent,
        pantalla: `${window.innerWidth}x${window.innerHeight} dpr=${window.devicePixelRatio}`,
        tactil: navigator.maxTouchPoints > 0,
        registro,
      })
      setEnviado('Enviado. Avísale a quien te lo pidió que ya puede revisarlo.')
    } catch (e) {
      setEnviado(`No se pudo enviar: ${e.message}`)
    } finally {
      setEnviando(false)
    }
  }

  const zonas = [
    {
      etiqueta: 'A · input encima a tamaño completo',
      nota: 'La técnica que usa el dashboard ahora.',
      render: () => (
        <div className="relative rounded-xl border border-dashed border-white/20 px-4 py-8 text-center">
          <span className="text-sm text-foreground">Toca aquí (A)</span>
          <input
            type="file"
            multiple
            aria-label="Prueba A"
            className="absolute inset-0 size-full cursor-pointer opacity-0"
            onClick={() => anotar('click en A')}
            onChange={alCambiar('A')}
          />
        </div>
      ),
    },
    {
      etiqueta: 'B · input visible sin estilos',
      nota: 'Lo más básico posible. Si esto falla, el problema es del navegador.',
      render: () => (
        <input
          type="file"
          multiple
          aria-label="Prueba B"
          className="w-full rounded-lg border border-white/20 p-2 text-sm"
          onClick={() => anotar('click en B')}
          onChange={alCambiar('B')}
        />
      ),
    },
    {
      etiqueta: 'C · botón que abre un input oculto por JavaScript',
      nota: 'La técnica que tenía antes y que se sospecha rota en Android.',
      render: () => (
        <>
          <Button
            variant="secondary"
            className="w-full"
            onClick={() => {
              anotar('click en boton C')
              refOculto.current?.click()
            }}
          >
            Toca aquí (C)
          </Button>
          <input
            ref={refOculto}
            type="file"
            multiple
            aria-label="Prueba C"
            className="hidden"
            onChange={alCambiar('C')}
          />
        </>
      ),
    },
  ]

  return (
    <div className="min-h-screen bg-background px-4 py-8">
      <div className="mx-auto max-w-lg">
        <h1 className="text-xl font-bold text-foreground">
          Diagnóstico del selector de archivos
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Prueba las tres opciones de abajo: en cada una elige tu PDF del banco.
          Abajo se va a ir llenando un registro. Cuando termines, toca{' '}
          <strong className="text-foreground">Enviar diagnóstico</strong>.
        </p>

        <div className="mt-6 space-y-5">
          {zonas.map((z) => (
            <div key={z.etiqueta}>
              <p className="mb-1.5 text-sm font-medium text-foreground">{z.etiqueta}</p>
              <p className="mb-2 text-xs text-muted-foreground">{z.nota}</p>
              {z.render()}
            </div>
          ))}
        </div>

        <div className="mt-8">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-foreground">
              Registro ({registro.length})
            </p>
            {registro.length > 0 && (
              <button
                type="button"
                onClick={() => setRegistro([])}
                className="text-xs text-muted-foreground underline"
              >
                Limpiar
              </button>
            )}
          </div>

          <pre
            className={cn(
              'mt-2 max-h-72 overflow-auto rounded-xl border border-white/10 bg-black/40 p-3',
              'font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-muted-foreground',
            )}
          >
            {registro.length === 0
              ? 'Todavía no pasó nada. Si tocas una opción, eliges un archivo y esto\nsigue vacío, ese es exactamente el problema que buscamos.'
              : registro.map((r, i) => `${r.t}  ${r.evento}\n${JSON.stringify(r, null, 1)}`).join('\n\n')}
          </pre>

          <div className="mt-3 rounded-xl border border-white/10 bg-white/3 p-3 font-mono text-[11px] break-all text-muted-foreground">
            {navigator.userAgent}
          </div>

          <Button className="mt-4 w-full" onClick={enviar} disabled={enviando}>
            <Send className="size-4" />
            {enviando ? 'Enviando…' : 'Enviar diagnóstico'}
          </Button>

          {enviado && (
            <p className="mt-3 rounded-lg border border-white/10 bg-white/3 px-3 py-2 text-sm text-foreground">
              {enviado}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
