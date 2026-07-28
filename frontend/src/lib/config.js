/**
 * Configuración pública que viene del backend en tiempo de ejecución.
 *
 * El número de WhatsApp se leía de `VITE_WHATSAPP_NUMBER`, que Vite incrusta al
 * compilar: cambiarlo obligaba a reconstruir y volver a desplegar el frontend.
 * Ahora se pide a `/api/config-publica` al cargar la app, así que cambiarlo es
 * editar una variable en Railway y reiniciar el backend.
 *
 * La variable de Vite se mantiene como respaldo para desarrollo local y para el
 * caso en que el backend no responda: la landing es pública y su botón principal
 * no puede quedar muerto porque la API esté caída.
 */

import { useEffect, useState } from 'react'

const RESPALDO = import.meta.env.VITE_WHATSAPP_NUMBER || ''
const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

let promesa = null

export function cargarConfigPublica() {
  if (!promesa) {
    promesa = fetch(`${API_URL}/api/config-publica`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => ({ whatsapp: d?.whatsapp_number || RESPALDO }))
      .catch(() => ({ whatsapp: RESPALDO }))
  }
  return promesa
}

/** Número de WhatsApp del dueño del producto. */
export function useWhatsapp() {
  const [numero, setNumero] = useState(RESPALDO)
  useEffect(() => {
    let activo = true
    cargarConfigPublica().then((c) => activo && setNumero(c.whatsapp))
    return () => {
      activo = false
    }
  }, [])
  return numero
}

/** Arma el enlace de WhatsApp con el mensaje ya escrito. */
export function enlaceWhatsapp(numero, mensaje) {
  if (!numero) return null
  return `https://wa.me/${numero}?text=${encodeURIComponent(mensaje)}`
}
