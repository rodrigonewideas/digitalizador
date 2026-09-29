import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/auth";

export function LoginPage() {
  const { user, login, confirmar2fa } = useAuth();
  const navigate = useNavigate();
  const [etapa, setEtapa] = useState<"senha" | "2fa">("senha");
  const [loginId, setLoginId] = useState("admin");
  const [senha, setSenha] = useState("");
  const [tokenDesafio, setTokenDesafio] = useState("");
  const [codigo, setCodigo] = useState("");
  const [erro, setErro] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function enviarSenha(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setBusy(true);
    try {
      const desafio = await login(loginId, senha);
      if (desafio === null) {
        // Modo dev: já autenticado, sem 2FA.
        navigate("/");
        return;
      }
      setTokenDesafio(desafio);
      setEtapa("2fa");
    } catch (err) {
      setErro(err instanceof ApiError ? err.detail : "Falha no login");
    } finally {
      setBusy(false);
    }
  }

  async function enviarCodigo(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setBusy(true);
    try {
      await confirmar2fa(tokenDesafio, codigo);
      navigate("/");
    } catch (err) {
      setErro(err instanceof ApiError ? err.detail : "Código inválido");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <div className="card login-card">
        <div className="login-brand">
          <span className="mark">◈</span> Digitalizador
        </div>
        <p className="muted" style={{ textAlign: "center", marginTop: 0 }}>
          Cemitério Parque Bonfim
        </p>

        {erro && <div className="alert err">{erro}</div>}

        {etapa === "senha" ? (
          <form className="stack" onSubmit={enviarSenha}>
            <div className="field">
              <label htmlFor="login">Usuário</label>
              <input id="login" value={loginId} onChange={(e) => setLoginId(e.target.value)} autoFocus />
            </div>
            <div className="field">
              <label htmlFor="senha">Senha</label>
              <input
                id="senha"
                type="password"
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
              />
            </div>
            <button className="btn" disabled={busy}>
              {busy ? "Entrando…" : "Entrar"}
            </button>
          </form>
        ) : (
          <form className="stack" onSubmit={enviarCodigo}>
            <div className="field">
              <label htmlFor="codigo">Código de verificação (2ª etapa)</label>
              <input
                id="codigo"
                inputMode="numeric"
                placeholder="000000"
                value={codigo}
                onChange={(e) => setCodigo(e.target.value)}
                autoFocus
              />
            </div>
            <button className="btn" disabled={busy}>
              {busy ? "Validando…" : "Confirmar"}
            </button>
            <button type="button" className="btn ghost sm" onClick={() => setEtapa("senha")}>
              Voltar
            </button>
            <p className="hint">
              Enviamos um código para o e-mail cadastrado. Em ambiente de desenvolvimento o código
              aparece no log do backend: <code>docker compose logs backend | grep -A3 DEV-EMAIL</code>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
