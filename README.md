# FinanzasIA

Plataforma web donde un dueño de negocio pequeño sube los PDFs o Excel de sus estados
de cuenta bancarios, la IA lee y categoriza cada movimiento, y arma un dashboard con
sus ingresos y gastos reales, la tendencia mes a mes y una proyección de cierre de año.

Los montos van en Soles (S/) y toda la interfaz está en español.

## En producción

| | URL |
|---|---|
| **App** | <https://finanzas-ia-lake.vercel.app> |
| API | <https://finanzas-ia-api.onrender.com> |
| Docs de la API | <https://finanzas-ia-api.onrender.com/docs> |
| Repositorio | <https://github.com/chocolatito27/finanzas-ia> |

El frontend está en Vercel y el backend en el plan gratuito de Render, que
**duerme tras 15 minutos sin tráfico**: la primera visita después de un rato
espera ~1 minuto a que despierte, y recién ahí empieza a procesar. Para quitarlo
hay que pasar a un plan pago (~$7/mes en Render, ~$5/mes en Railway).

Cada `git push` a `main` redespliega ambos automáticamente.

---

## Levantar el proyecto en local

Necesitas dos terminales: una para el backend y otra para el frontend.

### 1. Backend (FastAPI, puerto 8000)

```bash
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn main:app --reload --port 8000
```

Documentación interactiva de la API: <http://localhost:8000/docs>
Chequeo de configuración: <http://localhost:8000/api/salud>

### 2. Frontend (React + Vite, puerto 5173)

```bash
cd frontend
npm install
npm run dev
```

Abre <http://localhost:5173>.

---

## Variables de entorno

Ya están configuradas con valores reales en `backend/.env` y `frontend/.env.local`.
Ambos archivos están en `.gitignore`: **nunca los subas a un repositorio**.

Falta un dato por completar:

| Variable | Dónde | Qué poner |
|---|---|---|
| `WHATSAPP_NUMBER` | `backend/.env` | El número real de Tomás, formato internacional sin `+` (ej. `51987654321`) |
| `VITE_WHATSAPP_NUMBER` | `frontend/.env.local` | El mismo número |
| `ADMIN_EMAILS` / `VITE_ADMIN_EMAILS` | ambos | Los emails que pueden entrar a `/admin`. Hoy: `gustavo.araujot@unmsm.edu.pe` |

`CLAVE_ENCRYPTION_KEY` cifra la clave de los PDFs de cada usuario. **Si la cambias,
las claves ya guardadas dejan de poder descifrarse** y los usuarios tendrán que
volver a ingresarlas.

---

## Base de datos

El esquema ya está aplicado en el proyecto de Supabase `yfbronqatbidcktjygor`.

Para volver a aplicarlo (es idempotente):

```bash
set SUPABASE_ACCESS_TOKEN=sbp_...
set SUPABASE_PROJECT_REF=yfbronqatbidcktjygor
python sql/apply_schema.py
```

Tablas: `perfiles`, `archivos_procesados`, `movimientos`. Todas con Row Level
Security: cada usuario solo ve lo suyo. El backend usa la *service_role key*, que
hace bypass de RLS, por eso **cada consulta filtra explícitamente por `user_id`** —
la seguridad la garantiza el código, no la base.

Además hay dos protecciones en la base:

- Un trigger crea el perfil automáticamente al registrarse un usuario.
- Un trigger impide que un usuario se auto-active la suscripción: solo el backend
  (service_role) puede escribir la columna `activo`.

---

## Cómo funciona el procesamiento

```
PDF/Excel → extractor → IA (Venice/Claude) → Supabase → dashboard
```

### Extracción (`services/pdf_extractor.py`)

Cada banco maqueta su PDF distinto, así que el extractor trabaja en tres niveles:

1. **Por posición de columnas** — lee las palabras con sus coordenadas X, encuentra
   la fila de encabezados (`FECHA / DESCRIPCIÓN / CARGO / ABONO / SALDO`) y asigna
   cada importe a su columna. El signo sale de la columna, no de adivinar.
2. **Por saldo corrido** — si el estado trae columna de saldo, corrige el signo
   comparando el saldo con el de la línea anterior. Es el método más confiable.
3. **Por palabras clave** — último recurso: deduce el signo del texto
   (`PAGO`, `RETIRO` → gasto; `ABONO`, `DEPÓSITO` → ingreso).

Los PDFs con contraseña se abren con `pikepdf` usando la clave guardada (cifrada)
del usuario. Si no funciona, el frontend ofrece actualizarla.

### Categorización (`services/ia_categorizer.py`)

Se manda a Venice AI (modelo `claude-sonnet-4-6`) en lotes de 40 movimientos, con
hasta 2 reintentos por lote si devuelve JSON inválido. Si un lote falla del todo,
esos movimientos quedan como `DESCONOCIDO` en vez de perderse.

**La fecha y el monto nunca vienen del modelo.** Se conservan los valores del
extractor y del modelo solo se toman `categoria` y `descripcion_limpia`, así una
alucinación no puede corromper las cifras del dashboard. Además, si el modelo
clasifica un monto positivo como gasto (o al revés), se descarta su respuesta: el
signo lo decide el banco.

### Categorías

| Categoría | Significado |
|---|---|
| `INGRESO_VENTA` | Entrada de dinero por ventas |
| `INGRESO_TRANSFERENCIA` | Transferencia recibida de otra persona |
| `GASTO_PROVEEDOR` | Pago a proveedores, compra de stock |
| `GASTO_OPERATIVO` | Alquiler, servicios, luz, internet, comisiones, ITF |
| `GASTO_PERSONAL` | Retiro personal del dueño |
| `TRANSFERENCIA_INTERNA` | Entre cuentas propias — **excluida** de ingresos y gastos |
| `DESCONOCIDO` | No está claro; el usuario lo corrige desde la tabla |

---

## Pruebas

```bash
cd backend

# Genera estados de cuenta de ejemplo (BCP, Interbank, BBVA Excel, uno con clave)
.venv\Scripts\python tests\generar_ejemplos.py

# Extractores: sin llamar a la IA, no cuesta tokens
.venv\Scripts\python tests\probar_extractores.py

# Pipeline completo: extracción + categorización real con Venice
.venv\Scripts\python tests\probar_pipeline.py

# API end-to-end: login, subida, dashboard, filtros, corrección de categoría
# (requiere el backend corriendo)
.venv\Scripts\python tests\probar_api.py

# PDFs con contraseña: guardar la clave, abrir el PDF, y el caso de clave errada
.venv\Scripts\python tests\probar_pdf_protegido.py

# Serie temporal: eje sin saltos y proyección que ignora los meses vacíos
.venv\Scripts\python tests\probar_serie.py
```

### Las dos cuentas de prueba (importante)

Hay **dos** cuentas y no hay que confundirlas:

| Cuenta | Para qué | Riesgo |
|---|---|---|
| `prueba@finanzasia.test` / `prueba123456` | Explorar la app a mano | Ninguno: las pruebas no la tocan |
| `qa-automatizado@finanzasia.test` | Las pruebas automatizadas | **Lo que subas aquí se borra sin aviso** |

La primera la crea `tests/crear_usuario_prueba.py`; la segunda se crea sola la
primera vez que corres una prueba.

Esta separación existe por un accidente real: las pruebas corrían sobre la cuenta de
exploración y empezaban borrando *todos* sus archivos para ser repetibles, así que
se llevaron por delante un estado de cuenta que alguien había subido. Ahora
(`tests/_comun.py`) las pruebas usan su propia cuenta y solo borran archivos cuyo
nombre empieza con `ejemplo_` — nunca a ciegas.

Las pruebas escriben en la base de datos **real**. No las corras contra producción
con usuarios de verdad.

Para borrar cualquiera de las dos cuentas: Supabase → Authentication → Users
(sus movimientos se van en cascada).

---

## Flujo del producto

```
1. El usuario llega a la landing
   → clic en "Quiero suscribirme" → se abre WhatsApp con el mensaje listo
   → Tomás coordina el pago por Yape/Plin
   → Tomás entra a /admin y activa la cuenta

2. El usuario entra al app
   → login → onboarding (nombre del negocio + clave de sus PDFs)
   → sube sus estados de cuenta (varios meses a la vez)
   → espera 30–60 s mientras la IA procesa
   → ve su dashboard

3. Cada mes sube el nuevo estado de cuenta y el dashboard se actualiza
```

Mientras la cuenta no esté activa, el usuario ve una pantalla que lo manda a
WhatsApp; el backend además bloquea todos los endpoints de datos con 403.

---

## Decisiones de diseño que conviene conocer

**Los montos salen de la API como número, no como string.** Pydantic serializa
`Decimal` como texto para no perder precisión, y eso rompía los gráficos. Los
cálculos siguen en `Decimal`; la conversión ocurre solo al salir a JSON
(`Monto` en `models.py`).

**El mismo archivo no se procesa dos veces.** Se guarda el `sha256` del contenido y
hay un índice único por `(user_id, hash_archivo)`. Si el usuario vuelve a subir el
mismo PDF, se le avisa en vez de duplicarle los movimientos.

**"Mes actual" es el mes más reciente con datos**, no el del calendario. Si alguien
sube en julio el estado de cuenta de marzo, el resumen habla de marzo.

**El eje de tiempo se rellena, pero la proyección no.** Si el usuario tiene marzo y
junio, los gráficos muestran los cuatro meses con abril y mayo en cero — si no, las
dos barras quedarían pegadas como si fueran consecutivas y el gráfico mentiría sobre
la tendencia. La proyección, en cambio, promedia solo sobre los meses que sí tienen
movimientos: un mes vacío significa "no subió el estado de cuenta", no "facturó
cero", y meterlo al promedio lo hundiría.

**La proyección es promedio mensual × 12**, calculada sobre el año del último
movimiento. Con un solo mes de datos se muestra igual pero marcada como no
confiable, porque extrapolar un mes a doce no dice nada.

**Los colores de las series de los gráficos no son los mismos del texto.** El verde
y rojo del brief (`#10B981` / `#EF4444`) funcionan como texto etiquetado, pero como
barras contiguas quedan por debajo del umbral de separación para daltonismo
deuteranope. Las series usan `#199e70` / `#e66767`, validados contra el fondo real,
con leyenda, orden fijo y tooltip para que la identidad nunca dependa solo del color.

**El desglose por categoría es de barras horizontales de un solo color**, no de
torta con siete colores: con siete categorías, siete tonos obligan a ir y volver a
una leyenda y no hay siete que se distingan bien con daltonismo. El nombre va en el
eje y la longitud hace el trabajo.

---

## Deploy

Ya está desplegado; esto es para reconstruirlo o mover el proyecto.

### Frontend → Vercel

```bash
cd frontend
npx vercel --prod
```

Las variables **no se cargan con `vercel env add`**. Pasarle el valor por una
tubería de PowerShell le antepone un BOM (U+FEFF) invisible; ese carácter quedó
pegado al inicio de la clave de Supabase y el navegador rechazaba toda petición
con *"String contains non ISO-8859-1 code point"*, porque un header HTTP no
admite caracteres fuera de Latin-1. Usa el script, que además relee y verifica:

```bash
set VERCEL_TOKEN=...
python frontend/configurar_vercel_env.py
```

Se guardan como `plain` y no `encrypted` a propósito: todas terminan dentro del
JavaScript que descarga el navegador, así que no son secretas, y en claro se
pueden releer para comprobar que no traigan basura invisible.

### Backend → Render

Servicio `finanzas-ia-api`, tipo *web service*, runtime Python, `rootDir` =
`backend`, rama `main`, con auto-deploy activado.

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Las variables de entorno se cargan **en Render**, nunca en el repositorio: son
las mismas de `backend/.env`. Health check en `/api/salud`.

**`FRONTEND_ORIGINS` debe incluir el dominio de Vercel**, si no el navegador
bloquea todo por CORS. Hoy tiene los tres alias de producción más
`http://localhost:5173` para desarrollo. Ojo: los *preview deployments* de
Vercel usan dominios aleatorios que no están en la lista, así que solo funciona
producción.

---

## Estructura

```
finanzas-ia/
├── backend/
│   ├── main.py                     # app FastAPI + CORS + health check
│   ├── config.py                   # carga y valida el .env
│   ├── models.py                   # modelos Pydantic (incluye el tipo Monto)
│   ├── database.py                 # cliente Supabase y consultas
│   ├── security.py                 # auth (JWT de Supabase) y cifrado Fernet
│   ├── routers/
│   │   ├── auth.py                 # perfil y onboarding
│   │   ├── archivos.py             # subida y procesamiento
│   │   ├── movimientos.py          # dashboard, filtros, corrección
│   │   └── admin.py                # activar/desactivar usuarios
│   ├── services/
│   │   ├── pdf_extractor.py        # PDFs bancarios (pdfplumber + pikepdf)
│   │   ├── excel_extractor.py      # Excel y CSV (openpyxl)
│   │   └── ia_categorizer.py       # Venice AI / Claude
│   └── tests/
├── frontend/
│   └── src/
│       ├── pages/                  # Landing, Login, Register, Onboarding,
│       │                           # DashboardPage, AdminPage, SuscripcionInactiva
│       ├── components/
│       │   ├── graficos/           # GraficoBarras, CurvaTendencia,
│       │   │                       # ProyeccionAnual, GastosPorCategoria, tema
│       │   ├── ui/                 # componentes shadcn
│       │   ├── Layout.jsx
│       │   ├── UploadZone.jsx
│       │   └── MovimientosTabla.jsx
│       └── lib/                    # supabase, api, auth, utils
└── sql/
    ├── schema.sql
    └── apply_schema.py
```
