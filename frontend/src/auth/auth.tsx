import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api, jsonBody, tokens } from "../api/client";
import type { Usuario } from "../api/types";

interface LoginResposta {
  desafio_2fa: boolean;
  token_desafio?: string;
  access_token?: string;
  refresh_token?: string;
}

interface AuthState {
  user: Usuario | null;
  loading: boolean;
  /** Retorna o token de desafio se precisar de 2FA; null se já logou (modo dev). */
  login: (login: string, senha: string) => Promise<string | null>;
  confirmar2fa: (tokenDesafio: string, codigo: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Usuario | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      if (tokens.access) {
        try {
          setUser(await api<Usuario>("/usuarios/me"));
        } catch {
          tokens.clear();
        }
      }
      setLoading(false);
    })();
  }, []);

  async function login(login: string, senha: string): Promise<string | null> {
    const r = await api<LoginResposta>("/auth/login", jsonBody({ login, senha }), false);
    if (!r.desafio_2fa && r.access_token && r.refresh_token) {
      // Modo dev: 2FA desativado, já veio com tokens.
      tokens.set(r.access_token, r.refresh_token);
      setUser(await api<Usuario>("/usuarios/me"));
      return null;
    }
    return r.token_desafio ?? "";
  }

  async function confirmar2fa(tokenDesafio: string, codigo: string): Promise<void> {
    const r = await api<{ access_token: string; refresh_token: string }>(
      "/auth/2fa",
      jsonBody({ token_desafio: tokenDesafio, codigo }),
      false,
    );
    tokens.set(r.access_token, r.refresh_token);
    setUser(await api<Usuario>("/usuarios/me"));
  }

  async function logout(): Promise<void> {
    try {
      if (tokens.refresh) await api("/auth/logout", jsonBody({ refresh_token: tokens.refresh }));
    } catch {
      /* ignora */
    }
    tokens.clear();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, confirmar2fa, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth fora do AuthProvider");
  return ctx;
}
