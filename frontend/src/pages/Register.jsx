import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CheckCircle2, Loader2, MessageCircle } from 'lucide-react'

import { Marca } from '@/components/Layout'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { enlaceWhatsapp, useWhatsapp } from '@/lib/config'
import { supabase } from '@/lib/supabase'

const MENSAJE = 'Hola, acabo de crear mi cuenta en FinanzasIA y quiero activarla'

export default function Register() {
  const navegar = useNavigate()
  const ENLACE_WHATSAPP = enlaceWhatsapp(useWhatsapp(), MENSAJE)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState(null)
  const [necesitaConfirmar, setNecesitaConfirmar] = useState(false)

  async function registrar(evento) {
    evento.preventDefault()
    if (password.length < 6) {
      setError('La contraseña debe tener al menos 6 caracteres.')
      return
    }
    setCargando(true)
    setError(null)

    const { data, error: fallo } = await supabase.auth.signUp({ email, password })

    if (fallo) {
      setError(
        fallo.message.includes('already registered')
          ? 'Ese email ya tiene una cuenta. Inicia sesión.'
          : fallo.message,
      )
      setCargando(false)
      return
    }

    // Si el proyecto exige confirmar el email, no hay sesión todavía.
    if (!data.session) {
      setNecesitaConfirmar(true)
      setCargando(false)
      return
    }
    navegar('/onboarding')
  }

  if (necesitaConfirmar) {
    return (
      <div className="grid min-h-screen place-items-center bg-background px-4">
        <div className="w-full max-w-sm rounded-xl border border-white/10 bg-card p-7 text-center">
          <CheckCircle2 className="mx-auto size-9 text-emerald-400" />
          <h1 className="mt-4 text-xl font-semibold text-foreground">Revisa tu correo</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Te enviamos un enlace a <strong className="text-foreground">{email}</strong>{' '}
            para confirmar tu cuenta. Después de confirmarla, escríbenos por WhatsApp
            para activar tu suscripción.
          </p>
          <Button
            className="mt-6 w-full"
            render={<a href={ENLACE_WHATSAPP} target="_blank" rel="noreferrer" />}
          >
            <MessageCircle className="size-4" />
            Activar mi cuenta
          </Button>
          <Button variant="ghost" className="mt-2 w-full" render={<Link to="/login" />}>
            Ir a iniciar sesión
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="grid min-h-screen place-items-center bg-background px-4">
      <div className="w-full max-w-sm">
        <Link to="/" className="mb-8 flex justify-center">
          <Marca className="text-lg" />
        </Link>

        <div className="rounded-xl border border-white/10 bg-card p-7">
          <h1 className="text-xl font-semibold text-foreground">Crear cuenta</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Después de crearla, coordinamos la activación por WhatsApp.
          </p>

          <form onSubmit={registrar} className="mt-6 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="tu@correo.com"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Contraseña</Label>
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Mínimo 6 caracteres"
              />
            </div>

            {error && (
              <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-red-300">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full" disabled={cargando}>
              {cargando && <Loader2 className="size-4 animate-spin" />}
              Crear cuenta
            </Button>
          </form>
        </div>

        <p className="mt-5 text-center text-sm text-muted-foreground">
          ¿Ya tienes cuenta?{' '}
          <Link to="/login" className="text-acento-suave hover:underline">
            Inicia sesión
          </Link>
        </p>
      </div>
    </div>
  )
}
