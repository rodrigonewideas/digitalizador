import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth/auth";
import { Layout } from "./components/Layout";
import {
  CaracteristicasPage,
  GruposPage,
  IndicesAposPage,
  IndicesOriginalPage,
  MotivosPage,
  TiposDocumentoPage,
} from "./pages/Cadastros";
import { CertificadosPage } from "./pages/CertificadosPage";
import { ConsultaPage } from "./pages/ConsultaPage";
import { LoginPage } from "./pages/LoginPage";
import { ParametrosPage } from "./pages/ParametrosPage";
import { RegistroPage } from "./pages/RegistroPage";
import { UsuariosPage } from "./pages/UsuariosPage";

function Protected({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="center muted">Carregando…</div>;
  return user ? children : <Navigate to="/login" replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route path="/" element={<ConsultaPage />} />
        <Route path="/registros/:id" element={<RegistroPage />} />
        <Route path="/tabelas/tipos" element={<TiposDocumentoPage />} />
        <Route path="/tabelas/motivos" element={<MotivosPage />} />
        <Route path="/tabelas/indices-original" element={<IndicesOriginalPage />} />
        <Route path="/tabelas/indices-apos" element={<IndicesAposPage />} />
        <Route path="/tabelas/grupos" element={<GruposPage />} />
        <Route path="/tabelas/caracteristicas" element={<CaracteristicasPage />} />
        <Route path="/tabelas/usuarios" element={<UsuariosPage />} />
        <Route path="/tabelas/parametros" element={<ParametrosPage />} />
        <Route path="/certificados" element={<CertificadosPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
