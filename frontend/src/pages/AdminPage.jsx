/**
 * Panel de admin: ver quién se registró y activar/desactivar suscripciones.
 *
 * El acceso lo controla el backend con ADMIN_EMAILS; aquí solo se oculta el enlace.
 */

import { useCallback, useEffect, useState } from 'react'
import { AlertCircle, Loader2, Search } from 'lucide-react'

import Layout from '@/components/Layout'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { api } from '@/lib/api'
import { fechaPeru } from '@/lib/utils'

export default function AdminPage() {
  const [usuarios, setUsuarios] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [cambiando, setCambiando] = useState(null)
  const [busqueda, setBusqueda] = useState('')

  const cargar = useCallback(() => {
    setCargando(true)
    setError(null)
    api
      .usuarios()
      .then((datos) => setUsuarios(datos ?? []))
      .catch((e) => setError(e.message))
      .finally(() => setCargando(false))
  }, [])

  useEffect(cargar, [cargar])

  async function alternar(usuario) {
    setCambiando(usuario.id)
    setError(null)
    try {
      const actualizado = await api.cambiarEstadoUsuario(usuario.id, !usuario.activo)
      setUsuarios((previos) =>
        previos.map((u) => (u.id === actualizado.id ? actualizado : u)),
      )
    } catch (e) {
      setError(e.message)
    } finally {
      setCambiando(null)
    }
  }

  const termino = busqueda.trim().toLowerCase()
  const filtrados = termino
    ? usuarios.filter(
        (u) =>
          (u.email ?? '').toLowerCase().includes(termino) ||
          (u.nombre_negocio ?? '').toLowerCase().includes(termino),
      )
    : usuarios

  const activos = usuarios.filter((u) => u.activo).length

  return (
    <Layout>
      <h1 className="text-2xl font-bold text-foreground">Administración</h1>
      <p className="mt-1 text-muted-foreground">
        Activa la cuenta de un usuario cuando confirmes su pago por Yape o Plin.
      </p>

      {error && (
        <div className="mt-6 flex gap-2.5 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3">
          <AlertCircle className="size-4 shrink-0 text-red-400 mt-0.5" />
          <p className="text-sm text-red-300">{error}</p>
        </div>
      )}

      <Card className="mt-6 border-white/10">
        <CardHeader>
          <CardTitle>Usuarios</CardTitle>
          <CardDescription>
            {usuarios.length} registrados · {activos} con suscripción activa
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="relative mb-4 max-w-sm">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              placeholder="Buscar por email o negocio"
              className="pl-9"
            />
          </div>

          {cargando ? (
            <div className="grid place-items-center py-16">
              <Loader2 className="size-5 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-white/10">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent border-white/10">
                    <TableHead>Email</TableHead>
                    <TableHead>Negocio</TableHead>
                    <TableHead className="w-[120px]">Estado</TableHead>
                    <TableHead className="w-[110px] text-right">Movimientos</TableHead>
                    <TableHead className="w-[110px]">Registro</TableHead>
                    <TableHead className="w-[130px] text-right">Acción</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtrados.length === 0 && (
                    <TableRow>
                      <TableCell
                        colSpan={6}
                        className="py-10 text-center text-muted-foreground"
                      >
                        No hay usuarios que coincidan.
                      </TableCell>
                    </TableRow>
                  )}

                  {filtrados.map((u) => (
                    <TableRow key={u.id} className="border-white/8">
                      <TableCell className="text-foreground">{u.email ?? '—'}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {u.nombre_negocio ?? (
                          <span className="italic">sin configurar</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={
                            u.activo
                              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                              : 'border-white/12 bg-white/4 text-muted-foreground'
                          }
                        >
                          {u.activo ? 'Activo' : 'Inactivo'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono text-muted-foreground tabular">
                        {u.total_movimientos}
                      </TableCell>
                      <TableCell className="font-mono text-sm text-muted-foreground tabular">
                        {fechaPeru(u.created_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant={u.activo ? 'ghost' : 'default'}
                          disabled={cambiando === u.id}
                          onClick={() => alternar(u)}
                        >
                          {cambiando === u.id && (
                            <Loader2 className="size-3.5 animate-spin" />
                          )}
                          {u.activo ? 'Desactivar' : 'Activar'}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </Layout>
  )
}
