/**
 * Onboarding: nombre del negocio y clave de los PDFs bancarios.
 *
 * La clave (normalmente el DNI) viaja al backend y se guarda cifrada con Fernet;
 * nunca se muestra de vuelta. Es opcional: quien descarga PDFs sin contraseña puede
 * saltarla.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, ShieldCheck } from 'lucide-react'

import { Marca } from '@/components/Layout'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'

export default function Onboarding() {
  const navegar = useNavigate()
  const { perfil, recargarPerfil } = useAuth()
  const [nombreNegocio, setNombreNegocio] = useState(perfil?.nombre_negocio ?? '')
  const [clavePdf, setClavePdf] = useState('')
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState(null)

  async function guardar(evento) {
    evento.preventDefault()
    setCargando(true)
    setError(null)
    try {
      await api.guardarOnboarding({
        nombre_negocio: nombreNegocio.trim(),
        clave_pdf: clavePdf.trim() || null,
      })
      await recargarPerfil()
      navegar('/dashboard')
    } catch (e) {
      setError(e.message)
      setCargando(false)
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-background px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <Marca className="text-lg" />
        </div>

        <div className="rounded-xl border border-white/10 bg-card p-7">
          <h1 className="text-xl font-semibold text-foreground">Configura tu cuenta</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Solo dos datos y ya puedes subir tus estados de cuenta.
          </p>

          <form onSubmit={guardar} className="mt-6 space-y-5">
            <div className="space-y-2">
              <Label htmlFor="negocio">¿Cómo se llama tu negocio?</Label>
              <Input
                id="negocio"
                required
                maxLength={120}
                value={nombreNegocio}
                onChange={(e) => setNombreNegocio(e.target.value)}
                placeholder="Importaciones Tomás SAC"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="clave">
                Clave de tus PDFs del banco{' '}
                <span className="font-normal text-muted-foreground">(opcional)</span>
              </Label>
              <Input
                id="clave"
                type="password"
                maxLength={64}
                value={clavePdf}
                onChange={(e) => setClavePdf(e.target.value)}
                placeholder="Normalmente tu DNI"
              />
              <p className="flex gap-2 text-xs leading-relaxed text-muted-foreground">
                <ShieldCheck className="size-3.5 shrink-0 mt-0.5 text-emerald-400" />
                Se guarda cifrada y solo se usa para abrir tus PDFs protegidos. Si tus
                estados de cuenta no tienen contraseña, déjalo vacío.
              </p>
            </div>

            {error && (
              <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-red-300">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full" disabled={cargando}>
              {cargando && <Loader2 className="size-4 animate-spin" />}
              Continuar al dashboard
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}
