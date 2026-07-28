import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'

import { Marca } from '@/components/Layout'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { supabase } from '@/lib/supabase'

export default function Login() {
  const navegar = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState(null)

  async function entrar(evento) {
    evento.preventDefault()
    setCargando(true)
    setError(null)

    const { error: fallo } = await supabase.auth.signInWithPassword({ email, password })

    if (fallo) {
      setError(
        fallo.message === 'Invalid login credentials'
          ? 'Email o contraseña incorrectos.'
          : fallo.message,
      )
      setCargando(false)
      return
    }
    navegar('/dashboard')
  }

  return (
    <div className="grid min-h-screen place-items-center bg-background px-4">
      <div className="w-full max-w-sm">
        <Link to="/" className="mb-8 flex justify-center">
          <Marca className="text-lg" />
        </Link>

        <div className="rounded-xl border border-white/10 bg-card p-7">
          <h1 className="text-xl font-semibold text-foreground">Iniciar sesión</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Entra para ver tu dashboard.
          </p>

          <form onSubmit={entrar} className="mt-6 space-y-4">
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
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            {error && (
              <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-red-300">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full" disabled={cargando}>
              {cargando && <Loader2 className="size-4 animate-spin" />}
              Entrar
            </Button>
          </form>
        </div>

        <p className="mt-5 text-center text-sm text-muted-foreground">
          ¿No tienes cuenta?{' '}
          <Link to="/registro" className="text-acento-suave hover:underline">
            Créala aquí
          </Link>
        </p>
      </div>
    </div>
  )
}
