/**
 * Rutas de la app.
 *
 * Guardas de acceso, en orden:
 *   sin sesión              → /login
 *   sin onboarding          → /onboarding
 *   suscripción inactiva    → pantalla de activación (los admin la saltan)
 *   /admin sin ser admin    → /dashboard
 */

import { Suspense, lazy } from "react";
import { Loader2 } from "lucide-react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";

import Diagnostico from "@/pages/Diagnostico";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Onboarding from "@/pages/Onboarding";
import Register from "@/pages/Register";
import SinConexion from "@/pages/SinConexion";
import SuscripcionInactiva from "@/pages/SuscripcionInactiva";
import { ProveedorAuth, useAuth } from "@/lib/auth";

// Recharts pesa ~600 kB y solo se usa dentro del dashboard: se carga aparte para
// que la landing y el login no lo arrastren.
const DashboardPage = lazy(() => import("@/pages/DashboardPage"));
const AdminPage = lazy(() => import("@/pages/AdminPage"));

function Cargando() {
  return (
    <div className="grid min-h-screen place-items-center bg-background">
      <Loader2 className="size-6 animate-spin text-muted-foreground" />
    </div>
  );
}

function RutaPrivada({ children, soloAdmin = false }) {
  const {
    autenticado,
    cargando,
    activo,
    esAdmin,
    onboardingCompleto,
    perfilCargado,
    errorPerfil,
  } = useAuth();
  const { pathname } = useLocation();

  if (cargando) return <Cargando />;
  if (!autenticado) return <Navigate to="/login" replace />;
  // Si el perfil no cargó, no se puede deducir nada de él: mandar al onboarding
  // acá hacía que un servidor caído se viera como un onboarding pendiente.
  if (!perfilCargado && errorPerfil) return <SinConexion />;
  if (!onboardingCompleto && pathname !== "/onboarding") {
    return <Navigate to="/onboarding" replace />;
  }
  if (!activo) return <SuscripcionInactiva />;
  if (soloAdmin && !esAdmin) return <Navigate to="/dashboard" replace />;

  return children;
}

/** Login y registro redirigen al dashboard si ya hay sesión. */
function RutaPublica({ children }) {
  const { autenticado, cargando } = useAuth();
  if (cargando) return <Cargando />;
  if (autenticado) return <Navigate to="/dashboard" replace />;
  return children;
}

/** El onboarding solo exige sesión, no suscripción activa. */
function RutaOnboarding() {
  const { autenticado, cargando } = useAuth();
  if (cargando) return <Cargando />;
  if (!autenticado) return <Navigate to="/login" replace />;
  return <Onboarding />;
}

export default function App() {
  return (
    <BrowserRouter>
      <ProveedorAuth>
        <Suspense fallback={<Cargando />}>
          <Routes>
            <Route path="/" element={<Landing />} />

            <Route
              path="/login"
              element={
                <RutaPublica>
                  <Login />
                </RutaPublica>
              }
            />
            <Route
              path="/registro"
              element={
                <RutaPublica>
                  <Register />
                </RutaPublica>
              }
            />

            <Route path="/onboarding" element={<RutaOnboarding />} />

            {/* Pública a propósito: hay que poder abrirla desde el celular sin
                pelear con la sesión. No expone datos de nadie. */}
            <Route path="/diagnostico" element={<Diagnostico />} />

            <Route
              path="/dashboard"
              element={
                <RutaPrivada>
                  <DashboardPage />
                </RutaPrivada>
              }
            />
            <Route
              path="/admin"
              element={
                <RutaPrivada soloAdmin>
                  <AdminPage />
                </RutaPrivada>
              }
            />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </ProveedorAuth>
    </BrowserRouter>
  );
}
