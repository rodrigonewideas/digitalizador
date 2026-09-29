import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/auth";

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function sair() {
    await logout();
    navigate("/login");
  }

  return (
    <div className="app">
      <header className="header">
        <div className="topbar">
          <div className="brand">
            <span className="mark">◈</span> Digitalizador <span className="muted">Bonfim</span>
          </div>
          <div className="spacer" />
          <span className="user muted">
            {user?.nome || user?.login}
            {user?.is_admin ? " · admin" : ""}
          </span>
          <ThemeToggle />
          <button className="btn ghost sm" onClick={sair}>
            Sair
          </button>
        </div>

        <nav className="menubar">
          <NavLink to="/" end className="menuitem">
            Consulta
          </NavLink>
          <Dropdown label="Tabelas">
            <NavLink to="/tabelas/usuarios" className="menu-link">
              Usuários
            </NavLink>
            <NavLink to="/tabelas/grupos" className="menu-link">
              Setores
            </NavLink>
            <NavLink to="/tabelas/tipos" className="menu-link">
              Tipos de Documento
            </NavLink>
            <NavLink to="/tabelas/indices-original" className="menu-link">
              Índice Original
            </NavLink>
            <NavLink to="/tabelas/indices-apos" className="menu-link">
              Índice Após 1999
            </NavLink>
            <NavLink to="/tabelas/motivos" className="menu-link">
              Motivos
            </NavLink>
            <NavLink to="/tabelas/caracteristicas" className="menu-link">
              Características
            </NavLink>
            <NavLink to="/tabelas/parametros" className="menu-link">
              Parâmetros
            </NavLink>
          </Dropdown>
          <NavLink to="/certificados" className="menuitem">
            Certificados
          </NavLink>
        </nav>
      </header>

      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}

function Dropdown({ label, children }: { label: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="dropdown" onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        className={`menuitem${open ? " open" : ""}`}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {label} <span className="caret">▾</span>
      </button>
      {open && (
        <div className="menu" onClick={() => setOpen(false)}>
          {children}
        </div>
      )}
    </div>
  );
}

function ThemeToggle() {
  const [theme, setTheme] = useState<string>(() => localStorage.getItem("dig.theme") ?? "");

  useEffect(() => {
    const root = document.documentElement;
    if (theme) {
      root.setAttribute("data-theme", theme);
      localStorage.setItem("dig.theme", theme);
    } else {
      root.removeAttribute("data-theme");
      localStorage.removeItem("dig.theme");
    }
  }, [theme]);

  const atual =
    theme ||
    (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light");

  return (
    <button
      type="button"
      className="btn ghost sm"
      title="Alternar tema"
      aria-label="Alternar tema"
      onClick={() => setTheme(atual === "dark" ? "light" : "dark")}
    >
      {atual === "dark" ? "☀" : "☾"}
    </button>
  );
}
