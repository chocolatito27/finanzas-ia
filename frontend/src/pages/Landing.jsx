/**
 * Landing pública.
 *
 * El único CTA de compra es WhatsApp: no hay pasarela de pagos en esta versión,
 * el pago se coordina por Yape/Plin y Tomás activa la cuenta a mano.
 */

import { Link } from 'react-router-dom'
import { BarChart3, FileText, MessageCircle, Sparkles, TrendingUp } from 'lucide-react'

import { Marca } from '@/components/Layout'
import { Button } from '@/components/ui/button'
import { enlaceWhatsapp, useWhatsapp } from '@/lib/config'

const MENSAJE = 'Hola, quiero suscribirme a FinanzasIA'

const CARACTERISTICAS = [
  {
    Icono: FileText,
    titulo: 'Sube tu estado de cuenta',
    texto:
      'PDF o Excel del BCP, Interbank, BBVA o Scotiabank. Si tu PDF tiene clave, la guardamos cifrada y lo abrimos por ti.',
  },
  {
    Icono: Sparkles,
    titulo: 'La IA categoriza cada movimiento',
    texto:
      'Ventas, proveedores, gastos operativos, retiros personales. Las transferencias entre tus propias cuentas no se cuentan dos veces.',
  },
  {
    Icono: TrendingUp,
    titulo: 'Mira a dónde va tu año',
    texto:
      'Ingresos contra gastos mes a mes, la curva de tu tendencia y la proyección de cómo cierras el año.',
  },
]

export default function Landing() {
  const ENLACE_WHATSAPP = enlaceWhatsapp(useWhatsapp(), MENSAJE)

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-white/10">
        <div className="mx-auto flex h-16 max-w-6xl items-center px-4 sm:px-6">
          <Marca className="text-lg" />
          <div className="ml-auto flex items-center gap-2">
            <Button variant="ghost" render={<Link to="/login" />}>
              Iniciar sesión
            </Button>
            <Button variant="secondary" render={<Link to="/registro" />}>
              Crear cuenta
            </Button>
          </div>
        </div>
      </header>

      {/* --- Hero --- */}
      <section className="mx-auto max-w-6xl px-4 pt-20 pb-16 sm:px-6 sm:pt-28">
        <div className="max-w-3xl">
          <p className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/4 px-3 py-1 text-sm text-muted-foreground">
            <span className="size-1.5 rounded-full bg-primary" />
            Para negocios peruanos
          </p>

          <h1 className="mt-6 text-4xl font-bold leading-[1.1] tracking-tight text-foreground sm:text-6xl">
            Tus estados de cuenta,
            <br />
            convertidos en{' '}
            <span className="text-acento-suave">decisiones de negocio</span>.
          </h1>

          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground">
            Sube el PDF de tu banco y en menos de un minuto tienes cada movimiento
            categorizado, tus ingresos y gastos reales del mes, y una proyección de
            cómo vas a cerrar el año. Sin Excel, sin contador, sin adivinar.
          </p>

          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Button
              className="h-11 px-5 text-base"
              render={<a href={ENLACE_WHATSAPP} target="_blank" rel="noreferrer" />}
            >
              <MessageCircle className="size-4" />
              Quiero suscribirme
            </Button>
            <Button
              variant="secondary"
              className="h-11 px-5 text-base"
              render={<Link to="/login" />}
            >
              Ya tengo cuenta
            </Button>
          </div>

          <p className="mt-4 text-sm text-muted-foreground">
            Suscripción mensual. Coordinamos el pago por Yape o Plin por WhatsApp.
          </p>
        </div>
      </section>

      {/* --- 3 features --- */}
      <section className="mx-auto max-w-6xl px-4 pb-20 sm:px-6">
        <div className="grid gap-4 sm:grid-cols-3">
          {CARACTERISTICAS.map(({ Icono, titulo, texto }) => (
            <div key={titulo} className="rounded-xl border border-white/10 bg-card p-6">
              <span className="grid size-10 place-items-center rounded-xl bg-primary/12">
                <Icono className="size-5 text-acento-suave" />
              </span>
              <h3 className="mt-4 font-semibold text-foreground">{titulo}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{texto}</p>
            </div>
          ))}
        </div>
      </section>

      {/* --- CTA final --- */}
      <section className="mx-auto max-w-6xl px-4 pb-24 sm:px-6">
        <div className="rounded-xl border border-white/10 bg-card px-6 py-12 text-center sm:px-12">
          <BarChart3 className="mx-auto size-8 text-acento-suave" />
          <h2 className="mt-5 text-2xl font-bold text-foreground sm:text-3xl">
            Deja de cerrar el mes a ciegas
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-muted-foreground">
            Escríbenos por WhatsApp, coordinamos el pago y activamos tu cuenta el
            mismo día.
          </p>
          <Button
            className="mt-7 h-11 px-5 text-base"
            render={<a href={ENLACE_WHATSAPP} target="_blank" rel="noreferrer" />}
          >
            <MessageCircle className="size-4" />
            Hablar por WhatsApp
          </Button>
        </div>
      </section>

      <footer className="border-t border-white/10 py-8">
        <p className="text-center text-sm text-muted-foreground">
          FinanzasIA · Hecho en Perú · Montos en Soles (S/)
        </p>
      </footer>
    </div>
  )
}
