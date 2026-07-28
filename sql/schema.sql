-- ============================================================
-- FinanzasIA — Esquema de base de datos (Supabase / Postgres)
-- Ejecutar en el SQL Editor de Supabase o vía Management API.
-- Es idempotente: se puede volver a correr sin romper nada.
-- ============================================================

-- ------------------------------------------------------------
-- 1. PERFILES  (complementa auth.users de Supabase)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.perfiles (
  id            UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email         TEXT,
  nombre_negocio TEXT,
  clave_pdf     TEXT,                      -- cifrada con Fernet por el backend
  activo        BOOLEAN NOT NULL DEFAULT FALSE,  -- Tomás lo activa cuando el usuario paga
  onboarding_completo BOOLEAN NOT NULL DEFAULT FALSE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- 2. ARCHIVOS PROCESADOS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.archivos_procesados (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  nombre_archivo  TEXT NOT NULL,
  hash_archivo    TEXT,                    -- sha256 del contenido: evita reprocesar el mismo archivo
  banco_detectado TEXT,
  mes_inicio      DATE,
  mes_fin         DATE,
  total_movimientos INTEGER NOT NULL DEFAULT 0,
  estado          TEXT NOT NULL DEFAULT 'procesado',  -- procesado | error
  error_detalle   TEXT,
  procesado_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Un mismo usuario no puede tener dos veces el mismo archivo procesado con éxito
CREATE UNIQUE INDEX IF NOT EXISTS archivos_user_hash_uniq
  ON public.archivos_procesados (user_id, hash_archivo)
  WHERE hash_archivo IS NOT NULL;

CREATE INDEX IF NOT EXISTS archivos_user_idx
  ON public.archivos_procesados (user_id, procesado_at DESC);

-- ------------------------------------------------------------
-- 3. MOVIMIENTOS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.movimientos (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id              UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  archivo_id           UUID REFERENCES public.archivos_procesados(id) ON DELETE CASCADE,
  fecha                DATE NOT NULL,
  monto                DECIMAL(12,2) NOT NULL,   -- positivo = ingreso, negativo = gasto
  descripcion_original TEXT,
  descripcion_limpia   TEXT,
  categoria            TEXT NOT NULL DEFAULT 'DESCONOCIDO',
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT movimientos_categoria_check CHECK (categoria IN (
    'INGRESO_VENTA',
    'INGRESO_TRANSFERENCIA',
    'GASTO_PROVEEDOR',
    'GASTO_OPERATIVO',
    'GASTO_PERSONAL',
    'TRANSFERENCIA_INTERNA',
    'DESCONOCIDO'
  ))
);

CREATE INDEX IF NOT EXISTS movimientos_user_fecha_idx
  ON public.movimientos (user_id, fecha DESC);
CREATE INDEX IF NOT EXISTS movimientos_user_categoria_idx
  ON public.movimientos (user_id, categoria);

-- ------------------------------------------------------------
-- 4. ROW LEVEL SECURITY
--    Cada usuario solo ve lo suyo. El backend usa la service_role key,
--    que hace bypass de RLS, por eso puede escribir en nombre del usuario.
-- ------------------------------------------------------------
ALTER TABLE public.perfiles            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.archivos_procesados ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.movimientos         ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "perfil propio: leer"     ON public.perfiles;
DROP POLICY IF EXISTS "perfil propio: escribir" ON public.perfiles;
DROP POLICY IF EXISTS "perfil propio: crear"    ON public.perfiles;

CREATE POLICY "perfil propio: leer"     ON public.perfiles
  FOR SELECT USING (auth.uid() = id);
CREATE POLICY "perfil propio: crear"    ON public.perfiles
  FOR INSERT WITH CHECK (auth.uid() = id);
-- Ojo: el usuario NO puede cambiar 'activo' desde el cliente porque
-- solo el backend (service_role) escribe esa columna; ver trigger de abajo.
CREATE POLICY "perfil propio: escribir" ON public.perfiles
  FOR UPDATE USING (auth.uid() = id) WITH CHECK (auth.uid() = id);

DROP POLICY IF EXISTS "archivos propios: leer" ON public.archivos_procesados;
CREATE POLICY "archivos propios: leer" ON public.archivos_procesados
  FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "movimientos propios: leer"     ON public.movimientos;
DROP POLICY IF EXISTS "movimientos propios: escribir" ON public.movimientos;
CREATE POLICY "movimientos propios: leer" ON public.movimientos
  FOR SELECT USING (auth.uid() = user_id);
-- El usuario puede corregir la categoría de un movimiento mal clasificado
CREATE POLICY "movimientos propios: escribir" ON public.movimientos
  FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- ------------------------------------------------------------
-- 5. Blindaje: un usuario no puede auto-activarse la suscripción
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.proteger_campo_activo()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- auth.role() es 'service_role' cuando escribe el backend; ahí sí se permite.
  IF NEW.activo IS DISTINCT FROM OLD.activo
     AND COALESCE(auth.role(), '') <> 'service_role' THEN
    NEW.activo := OLD.activo;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_proteger_activo ON public.perfiles;
CREATE TRIGGER trg_proteger_activo
  BEFORE UPDATE ON public.perfiles
  FOR EACH ROW EXECUTE FUNCTION public.proteger_campo_activo();

-- ------------------------------------------------------------
-- 6. Crear el perfil automáticamente al registrarse un usuario
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.perfiles (id, email)
  VALUES (NEW.id, NEW.email)
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Backfill para usuarios que ya existan
INSERT INTO public.perfiles (id, email)
SELECT u.id, u.email FROM auth.users u
ON CONFLICT (id) DO NOTHING;
