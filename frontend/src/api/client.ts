// Base da API. Se VITE_API_URL não for definido, usa o MESMO host de onde o
// frontend foi servido (funciona por localhost ou por IP na rede), porta 18080.
export const API_BASE: string =
  (import.meta.env.VITE_API_URL as string | undefined) ??
  `${window.location.protocol}//${window.location.hostname}:18080/api/v1`;

const K_ACCESS = "dig.access";
const K_REFRESH = "dig.refresh";

export const tokens = {
  get access(): string | null {
    return localStorage.getItem(K_ACCESS);
  },
  get refresh(): string | null {
    return localStorage.getItem(K_REFRESH);
  },
  set(access: string, refresh: string): void {
    localStorage.setItem(K_ACCESS, access);
    localStorage.setItem(K_REFRESH, refresh);
  },
  clear(): void {
    localStorage.removeItem(K_ACCESS);
    localStorage.removeItem(K_REFRESH);
  },
};

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
  }
}

function withAuth(opts: RequestInit, auth: boolean): RequestInit {
  const headers = new Headers(opts.headers);
  if (auth && tokens.access) headers.set("Authorization", `Bearer ${tokens.access}`);
  return { ...opts, headers };
}

async function refreshTokens(): Promise<boolean> {
  if (!tokens.refresh) return false;
  const res = await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: tokens.refresh }),
  });
  if (!res.ok) {
    tokens.clear();
    return false;
  }
  const data = (await res.json()) as { access_token: string; refresh_token: string };
  tokens.set(data.access_token, data.refresh_token);
  return true;
}

export async function api<T = unknown>(
  path: string,
  opts: RequestInit = {},
  auth = true,
): Promise<T> {
  let res = await fetch(`${API_BASE}${path}`, withAuth(opts, auth));
  if (res.status === 401 && auth && (await refreshTokens())) {
    res = await fetch(`${API_BASE}${path}`, withAuth(opts, auth));
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = (await res.json()) as { detail?: unknown };
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* corpo não-JSON */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") ?? "";
  return (ct.includes("application/json") ? await res.json() : await res.blob()) as T;
}

export function jsonBody(payload: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
}
