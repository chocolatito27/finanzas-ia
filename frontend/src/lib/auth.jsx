/**
 * Contexto de sesión: envuelve Supabase Auth y el perfil del backend.
 *
 * Se expone un solo hook `useAuth()` con todo lo que las páginas necesitan
 * (sesión, perfil, si está activo, si es admin) para no repetir la lógica.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { api } from './api'
import { esAdmin, supabase } from './supabase'

const ContextoAuth = createContext(null)

export function ProveedorAuth({ children }) {
  const [sesion, setSesion] = useState(null)
  const [perfil, setPerfil] = useState(null)
  const [cargando, setCargando] = useState(true)

  const recargarPerfil = useCallback(async () => {
    try {
      setPerfil(await api.perfil())
    } catch {
      // Sin perfil la app sigue: el onboarding lo creará.
      setPerfil(null)
    }
  }, [])

  useEffect(() => {
    let activo = true

    supabase.auth.getSession().then(({ data }) => {
      if (!activo) return
      setSesion(data.session)
      if (!data.session) setCargando(false)
    })

    const { data: suscripcion } = supabase.auth.onAuthStateChange((_evento, nuevaSesion) => {
      setSesion(nuevaSesion)
      if (!nuevaSesion) {
        setPerfil(null)
        setCargando(false)
      }
    })

    return () => {
      activo = false
      suscripcion.subscription.unsubscribe()
    }
  }, [])

  useEffect(() => {
    if (!sesion) return
    let activo = true
    setCargando(true)
    recargarPerfil().finally(() => {
      if (activo) setCargando(false)
    })
    return () => {
      activo = false
    }
  }, [sesion, recargarPerfil])

  const cerrarSesion = useCallback(async () => {
    await supabase.auth.signOut()
    setPerfil(null)
  }, [])

  const valor = useMemo(() => {
    const email = sesion?.user?.email ?? null
    return {
      sesion,
      usuario: sesion?.user ?? null,
      email,
      perfil,
      cargando,
      autenticado: !!sesion,
      // El admin entra siempre, aunque su propio perfil no esté marcado activo.
      esAdmin: esAdmin(email) || !!perfil?.es_admin,
      activo: !!perfil?.activo || esAdmin(email),
      onboardingCompleto: !!perfil?.onboarding_completo,
      recargarPerfil,
      cerrarSesion,
    }
  }, [sesion, perfil, cargando, recargarPerfil, cerrarSesion])

  return <ContextoAuth.Provider value={valor}>{children}</ContextoAuth.Provider>
}

export function useAuth() {
  const contexto = useContext(ContextoAuth)
  if (!contexto) throw new Error('useAuth debe usarse dentro de <ProveedorAuth>')
  return contexto
}
