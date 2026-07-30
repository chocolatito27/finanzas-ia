/**
 * Cliente del backend FastAPI.
 *
 * Cada petición adjunta el access token de Supabase. Si el backend responde 403
 * porque la suscripción no está activa, se lanza un ErrorApi con `suscripcionInactiva`
 * para que la UI muestre la pantalla de "activa tu cuenta" en vez de un error genérico.
 */

import { supabase } from './supabase'

const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

export class ErrorApi extends Error {
  constructor(mensaje, estado) {
    super(mensaje)
    this.name = 'ErrorApi'
    this.estado = estado
  }

  get suscripcionInactiva() {
    return this.estado === 403
  }

  get sesionExpirada() {
    return this.estado === 401
  }
}

async function token() {
  const { data } = await supabase.auth.getSession()
  return data.session?.access_token || null
}

async function pedir(ruta, { metodo = 'GET', cuerpo, esFormData = false } = {}) {
  const accessToken = await token()
  const headers = {}
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`
  if (cuerpo && !esFormData) headers['Content-Type'] = 'application/json'

  let respuesta
  try {
    respuesta = await fetch(`${API_URL}${ruta}`, {
      method: metodo,
      headers,
      body: esFormData ? cuerpo : cuerpo ? JSON.stringify(cuerpo) : undefined,
    })
  } catch {
    throw new ErrorApi(
      'No se pudo conectar con el servidor. ¿Está corriendo el backend?',
      0,
    )
  }

  if (respuesta.status === 204) return null

  const texto = await respuesta.text()
  let datos = null
  try {
    datos = texto ? JSON.parse(texto) : null
  } catch {
    datos = null
  }

  if (!respuesta.ok) {
    const detalle = datos?.detail
    // Los errores de validación de FastAPI vienen como lista; se incluye el nombre
    // del campo para que el mensaje no sea un "Field required" sin contexto.
    const mensaje =
      typeof detalle === 'string'
        ? detalle
        : Array.isArray(detalle)
          ? detalle
              .map((d) => {
                const campo = Array.isArray(d.loc) ? d.loc.at(-1) : null
                return campo ? `${campo}: ${d.msg}` : d.msg
              })
              .join(' · ')
          : `Error ${respuesta.status}`
    throw new ErrorApi(mensaje, respuesta.status)
  }

  return datos
}

export const api = {
  // --- perfil ---
  perfil: () => pedir('/api/auth/perfil'),
  guardarOnboarding: (datos) =>
    pedir('/api/auth/onboarding', { metodo: 'POST', cuerpo: datos }),
  actualizarClavePdf: (clave_pdf) =>
    pedir('/api/auth/clave-pdf', { metodo: 'POST', cuerpo: { clave_pdf } }),

  // --- archivos ---
  subirArchivos: (archivos) => {
    const formData = new FormData()
    for (const archivo of archivos) formData.append('archivos', archivo)
    return pedir('/api/archivos/subir', {
      metodo: 'POST',
      cuerpo: formData,
      esFormData: true,
    })
  },
  listarArchivos: () => pedir('/api/archivos'),
  borrarArchivo: (id) => pedir(`/api/archivos/${id}`, { metodo: 'DELETE' }),

  // --- dashboard ---
  dashboard: () => pedir('/api/movimientos/dashboard'),
  serie: (granularidad = 'mes') =>
    pedir(`/api/movimientos/serie?granularidad=${granularidad}`),
  movimientos: ({ categoria, mes, limite = 500 } = {}) => {
    const params = new URLSearchParams()
    if (categoria) params.set('categoria', categoria)
    if (mes) params.set('mes', mes)
    params.set('limite', String(limite))
    return pedir(`/api/movimientos?${params}`)
  },
  cambiarCategoria: (id, categoria) =>
    pedir(`/api/movimientos/${id}/categoria`, {
      metodo: 'PATCH',
      cuerpo: { categoria },
    }),

  // --- admin ---
  usuarios: () => pedir('/api/admin/usuarios'),
  cambiarEstadoUsuario: (id, activo) =>
    pedir(`/api/admin/usuarios/${id}/estado`, {
      metodo: 'PATCH',
      cuerpo: { activo },
    }),

  // --- público ---
  configPublica: () => pedir('/api/config-publica'),

  // Diagnóstico del selector de archivos en celular (ver pages/Diagnostico.jsx)
  enviarDiagnostico: (datos) =>
    pedir('/api/diagnostico', { metodo: 'POST', cuerpo: datos }),
}
