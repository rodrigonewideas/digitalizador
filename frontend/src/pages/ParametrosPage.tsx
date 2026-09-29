import { useEffect, useState } from "react";

import { api, ApiError } from "../api/client";

type Parametros = Record<string, any>;

export function ParametrosPage() {
  const [p, setP] = useState<Parametros | null>(null);
  const [msg, setMsg] = useState<{ t: "ok" | "err"; s: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Parametros>("/parametros")
      .then(setP)
      .catch((e) => setMsg({ t: "err", s: e instanceof ApiError ? e.detail : "Falha ao carregar" }));
  }, []);

  function set(k: string, v: any) {
    setP((prev) => ({ ...(prev ?? {}), [k]: v }));
  }

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    if (!p) return;
    setBusy(true);
    setMsg(null);
    try {
      const atualizado = await api<Parametros>("/parametros", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          integracao_modo: p.integracao_modo,
          locacao_atual: p.locacao_atual || null,
          volume_gravacao_id: numOrNull(p.volume_gravacao_id),
          volume_backup_id: numOrNull(p.volume_backup_id),
          volume_thumbnail_id: numOrNull(p.volume_thumbnail_id),
          gravacao_datacenter: !!p.gravacao_datacenter,
          backup_datacenter: !!p.backup_datacenter,
        }),
      });
      setP(atualizado);
      setMsg({ t: "ok", s: "Parâmetros salvos." });
    } catch (err) {
      setMsg({ t: "err", s: err instanceof ApiError ? err.detail : "Falha ao salvar" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <p className="eyebrow">Tabelas</p>
        <h1>Parâmetros</h1>
        <p className="muted">Configurações globais de guarda e integração.</p>
      </div>

      {msg && <div className={`alert ${msg.t === "ok" ? "ok" : "err"}`}>{msg.s}</div>}

      {p && (
        <div className="card">
          <form className="row" onSubmit={salvar}>
            <div className="field">
              <label>Modo de integração (pdv_bonfim)</label>
              <select
                value={p.integracao_modo ?? "direct_db"}
                onChange={(e) => set("integracao_modo", e.target.value)}
              >
                <option value="direct_db">Banco direto (direct_db)</option>
                <option value="api">API REST (api)</option>
                <option value="desativado">Desativado</option>
              </select>
            </div>
            <div className="field">
              <label>Locação atual</label>
              <input value={p.locacao_atual ?? ""} onChange={(e) => set("locacao_atual", e.target.value)} />
            </div>
            <div className="field">
              <label>Volume gravação (ID)</label>
              <input type="number" value={p.volume_gravacao_id ?? ""} onChange={(e) => set("volume_gravacao_id", e.target.value)} />
            </div>
            <div className="field">
              <label>Volume backup (ID)</label>
              <input type="number" value={p.volume_backup_id ?? ""} onChange={(e) => set("volume_backup_id", e.target.value)} />
            </div>
            <div className="field">
              <label>Volume thumbnail (ID)</label>
              <input type="number" value={p.volume_thumbnail_id ?? ""} onChange={(e) => set("volume_thumbnail_id", e.target.value)} />
            </div>
            <div className="field">
              <label>Gravação no datacenter</label>
              <label style={{ display: "flex", gap: ".4rem", alignItems: "center" }}>
                <input type="checkbox" style={{ width: "auto" }} checked={!!p.gravacao_datacenter} onChange={(e) => set("gravacao_datacenter", e.target.checked)} />
                Sim
              </label>
            </div>
            <div className="field">
              <label>Backup no datacenter</label>
              <label style={{ display: "flex", gap: ".4rem", alignItems: "center" }}>
                <input type="checkbox" style={{ width: "auto" }} checked={!!p.backup_datacenter} onChange={(e) => set("backup_datacenter", e.target.checked)} />
                Sim
              </label>
            </div>
            <button className="btn" disabled={busy}>
              {busy ? "…" : "Salvar"}
            </button>
          </form>
        </div>
      )}
    </>
  );
}

function numOrNull(v: any): number | null {
  return v === "" || v == null ? null : Number(v);
}
