import { useEffect, useState } from "react";

import { api, API_BASE, ApiError, tokens } from "../api/client";
import type { Certificado } from "../api/types";

export function CertificadosPage() {
  const [lista, setLista] = useState<Certificado[]>([]);
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [senha, setSenha] = useState("");
  const [msg, setMsg] = useState<{ t: "ok" | "err"; s: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function carregar() {
    setLista(await api<Certificado[]>("/certificados"));
  }

  useEffect(() => {
    carregar().catch(() => setMsg({ t: "err", s: "Falha ao carregar certificados" }));
  }, []);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    if (!arquivo) return;
    setBusy(true);
    setMsg(null);
    try {
      const fd = new FormData();
      fd.append("file", arquivo);
      fd.append("senha", senha);
      const res = await fetch(`${API_BASE}/certificados`, {
        method: "POST",
        headers: { Authorization: `Bearer ${tokens.access ?? ""}` },
        body: fd,
      });
      if (!res.ok) {
        const j = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new ApiError(res.status, j.detail ?? "Falha ao enviar certificado");
      }
      setArquivo(null);
      setSenha("");
      setMsg({ t: "ok", s: "Certificado cadastrado." });
      await carregar();
    } catch (err) {
      setMsg({ t: "err", s: err instanceof ApiError ? err.detail : "Falha ao enviar" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <p className="eyebrow">Assinatura digital</p>
        <h1>Certificados A1</h1>
        <p className="muted">Seus certificados (.pfx) para assinar documentos. Guardados cifrados.</p>
      </div>

      {msg && <div className={`alert ${msg.t === "ok" ? "ok" : "err"}`}>{msg.s}</div>}

      <div className="card">
        <h2>Enviar certificado</h2>
        <form className="row" onSubmit={enviar}>
          <div className="field" style={{ flex: 2 }}>
            <label>Arquivo .pfx / PKCS#12</label>
            <input
              type="file"
              accept=".pfx,.p12"
              onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
            />
          </div>
          <div className="field">
            <label>Senha do certificado</label>
            <input type="password" value={senha} onChange={(e) => setSenha(e.target.value)} />
          </div>
          <button className="btn" disabled={busy || !arquivo}>
            {busy ? "Enviando…" : "Enviar"}
          </button>
        </form>
      </div>

      <div className="card" style={{ padding: 0 }}>
        {lista.length === 0 ? (
          <p className="empty">Nenhum certificado cadastrado.</p>
        ) : (
          <div className="tablewrap" style={{ border: "none" }}>
            <table>
              <thead>
                <tr>
                  <th>Titular</th>
                  <th>CPF/CNPJ</th>
                  <th>Emissor</th>
                  <th>Validade</th>
                  <th>Situação</th>
                </tr>
              </thead>
              <tbody>
                {lista.map((c) => (
                  <tr key={c.id}>
                    <td>{c.nome_titular ?? "—"}</td>
                    <td className="num">{c.cpf_cnpj ?? "—"}</td>
                    <td>{c.emissor ?? "—"}</td>
                    <td>{c.validade_fim ? c.validade_fim.slice(0, 10) : "—"}</td>
                    <td>
                      <span className={`pill ${c.ativo ? "accent" : "crit"}`}>
                        {c.ativo ? "ativo" : "inativo"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
