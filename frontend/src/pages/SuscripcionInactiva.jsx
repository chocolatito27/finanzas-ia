/** Pantalla para el usuario registrado cuya suscripción todavía no fue activada. */

import { Clock, MessageCircle, RefreshCw } from 'lucide-react'

import { Marca } from '@/components/Layout'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/auth'
import { enlaceWhatsapp, useWhatsapp } from '@/lib/config'

export default function SuscripcionInactiva() {
  const { email, recargarPerfil, cerrarSesion } = useAuth()
  const enlace = enlaceWhatsapp(
    useWhatsapp(),
    `Hola, quiero activar mi suscripción a FinanzasIA. Mi cuenta es ${email}`,
  )

  return (
    <div className="grid min-h-screen place-items-center bg-background px-4">
      <div className="w-full max-w-md text-center">
        <div className="mb-8 flex justify-center">
          <Marca className="text-lg" />
        </div>

        <div className="rounded-xl border border-white/10 bg-card p-8">
          <span className="mx-auto grid size-12 place-items-center rounded-xl bg-amber-500/12">
            <Clock className="size-6 text-amber-400" />
          </span>

          <h1 className="mt-5 text-xl font-semibold text-foreground">
            Tu cuenta está pendiente de activación
          </h1>
          <p className="mt-2.5 text-sm leading-relaxed text-muted-foreground">
            Ya creaste tu cuenta con{' '}
            <strong className="text-foreground">{email}</strong>. Escríbenos por
            WhatsApp para coordinar el pago por Yape o Plin y la activamos el mismo día.
          </p>

          <Button
            className="mt-7 w-full"
            render={<a href={enlace} target="_blank" rel="noreferrer" />}
          >
            <MessageCircle className="size-4" />
            Escribir por WhatsApp
          </Button>

          <Button variant="secondary" className="mt-2 w-full" onClick={recargarPerfil}>
            <RefreshCw className="size-4" />
            Ya pagué, revisar de nuevo
          </Button>

          <Button variant="ghost" className="mt-2 w-full" onClick={cerrarSesion}>
            Cerrar sesión
          </Button>
        </div>
      </div>
    </div>
  )
}
