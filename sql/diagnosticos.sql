-- ============================================================
-- Tabla para los diagnósticos del selector de archivos en celular.
--
-- Existe porque un fallo que solo ocurre en Chrome de Android no se puede
-- reproducir en escritorio: sin datos del dispositivo real, cada arreglo es
-- una adivinanza. La página /diagnostico escribe acá.
--
-- Es temporal. Cuando el problema esté cerrado, borrar la tabla y el endpoint.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.diagnosticos (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  agente     TEXT,
  pantalla   TEXT,
  tactil     BOOLEAN,
  registro   JSONB,
  creado_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS diagnosticos_creado_idx
  ON public.diagnosticos (creado_at DESC);

-- Solo el backend (service_role) escribe y lee. Nadie más necesita verlo.
ALTER TABLE public.diagnosticos ENABLE ROW LEVEL SECURITY;
