/**
 * Pantalla para cuando no se pudo cargar el perfil del usuario.
 *
 * Antes, si la petición del perfil fallaba, la app asumía que el onboarding
 * estaba pendiente y mandaba al usuario a rellenarlo. Eso confundía dos cosas
 * muy distintas: "todavía no configuraste tu negocio" y "no puedo hablar con el
 * servidor". Acá se dice lo segundo, con el detalle real y un botón para
 * reintentar.
 */

import { CloudOff, LogOut, RefreshCw } from 'lucide-react'

import { Marca } from '@/components/Layout'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/auth'

export default function SinConexion() {
  const { errorPerfil, recargarPerfil, cerrarSesion } = useAuth()

  // El backend en plan gratuito duerme; la primera petición del día puede
  // agotar el tiempo de espera y esto es lo que ve el usuario.
  const esCaida = errorPerfil?.estado === 0 || errorPerfil?.estado >= 500

  return (
    <div className="grid min-h-screen place-items-center bg-background px-4">
      <div className="w-full max-w-md text-center">
        <div className="mb-8 flex justify-center">
          <Marca className="text-lg" />
        </div>

        <div className="rounded-xl border border-white/10 bg-card p-8">
          <span className="mx-auto grid size-12 place-items-center rounded-xl bg-amber-500/12">
            <CloudOff className="size-6 text-amber-400" />
          </span>

          <h1 className="mt-5 text-xl font-semibold text-foreground">
            No pudimos cargar tu cuenta
          </h1>

          <p className="mt-2.5 text-sm leading-relaxed text-muted-foreground">
            {esCaida
              ? 'El servidor no está respondiendo. Si es la primera vez que entras hoy, puede tardar hasta un minuto en despertar: espera un momento y vuelve a intentarlo.'
              : 'Hubo un problema al conectar con el servidor. Revisa tu conexión a internet y vuelve a intentarlo.'}
          </p>

          {errorPerfil?.message && (
            <p className="mt-3 rounded-lg border border-white/10 bg-white/3 px-3 py-2 text-xs text-muted-foreground">
              {errorPerfil.message}
            </p>
          )}

          <Button className="mt-7 w-full" onClick={recargarPerfil}>
            <RefreshCw className="size-4" />
            Volver a intentar
          </Button>

          <Button variant="ghost" className="mt-2 w-full" onClick={cerrarSesion}>
            <LogOut className="size-4" />
            Cerrar sesión
          </Button>
        </div>
      </div>
    </div>
  )
}
