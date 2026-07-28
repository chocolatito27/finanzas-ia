/** Cabecera y contenedor de las páginas privadas. */

import { Link, useLocation, useNavigate } from 'react-router-dom'
import { LayoutDashboard, LogOut, Shield, Sparkles } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/auth'
import { cn } from '@/lib/utils'

export function Marca({ className }) {
  return (
    <span className={cn('flex items-center gap-2 font-semibold', className)}>
      <span className="grid size-7 place-items-center rounded-lg bg-primary">
        <Sparkles className="size-4 text-white" />
      </span>
      FinanzasIA
    </span>
  )
}

export default function Layout({ children }) {
  const { email, perfil, esAdmin, cerrarSesion } = useAuth()
  const navegar = useNavigate()
  const { pathname } = useLocation()

  async function salir() {
    await cerrarSesion()
    navegar('/')
  }

  const enlaces = [
    { a: '/dashboard', texto: 'Dashboard', Icono: LayoutDashboard },
    ...(esAdmin ? [{ a: '/admin', texto: 'Admin', Icono: Shield }] : []),
  ]

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b border-white/10 bg-background/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4 sm:px-6">
          <Link to="/dashboard">
            <Marca />
          </Link>

          <nav className="flex items-center gap-1">
            {enlaces.map(({ a, texto, Icono }) => (
              <Link
                key={a}
                to={a}
                className={cn(
                  'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors',
                  pathname === a
                    ? 'bg-white/8 text-foreground'
                    : 'text-muted-foreground hover:text-foreground hover:bg-white/5',
                )}
              >
                <Icono className="size-4" />
                {texto}
              </Link>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <div className="hidden text-right sm:block">
              {perfil?.nombre_negocio && (
                <p className="text-sm leading-tight text-foreground">
                  {perfil.nombre_negocio}
                </p>
              )}
              <p className="text-xs leading-tight text-muted-foreground">{email}</p>
            </div>
            <Button variant="ghost" size="sm" onClick={salir} aria-label="Cerrar sesión">
              <LogOut className="size-4" />
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">{children}</main>
    </div>
  )
}
