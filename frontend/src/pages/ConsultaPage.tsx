import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, ApiError } from "../api/client";
import type { RegistroBusca } from "../api/types";

export function ConsultaPage() {
  const navigate = useNavigate();
  const [lote, setLote] = useState("");
  const [contrato, setContrato] = useState("");
  const [registroId, setRegistroId] = useState("");
  const [resultados, setResultados] = useState<RegistroBusca[] | null>(null);
  const [erro, setErro] = useState("");
  const [busy, setBusy] = useState(false);

  async function buscar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    const params = new URLSearchParams();
    if (lote) params.set("lote", lote);
    if (contrato) params.set("contrato", contrato);
    if (registroId) params.set("registro_id", registroId);
    if ([...params.keys()].length === 0) {
      setErro("Informe ao menos um filtro: lote, contrato ou nº do registro.");
      return;
    }
    setBusy(true);
    try {
      setResultados(await api<RegistroBusca[]>(`/registros?${params.toString()}`));
    } catch (err) {
      setErro(err instanceof ApiError ? err.detail : "Falha na busca");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <p className="eyebrow">Painel de manipulação</p>
        <h1>Consulta de documentos</h1>
        <p className="muted">Filtre por lote, contrato ou nº do registro para ver os documentos.</p>
      </div>

      <div className="card">
        <form className="row" onSubmit={buscar}>
          <div className="field">
            <label htmlFor="lote">Nº do lote</label>
            <input id="lote" value={lote} onChange={(e) => setLote(e.target.value)} placeholder="1431" />
          </div>
          <div className="field">
            <label htmlFor="contrato">Contrato</label>
            <input id="contrato" value={contrato} onChange={(e) => setContrato(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="reg">Nº do registro</label>
            <input id="reg" value={registroId} onChange={(e) => setRegistroId(e.target.value)} />
          </div>
          <button className="btn" disabled={busy}>
            {busy ? "Buscando…" : "Filtrar"}
          </button>
        </form>
        {erro && <div className="alert err">{erro}</div>}
      </div>

      {resultados && (
        <div className="card" style={{ padding: 0 }}>
          {resultados.length === 0 ? (
            <p className="empty">Nenhum registro encontrado para o filtro.</p>
          ) : (
            <div className="tablewrap" style={{ border: "none" }}>
              <table>
                <thead>
                  <tr>
                    <th>Registro</th>
                    <th>Contrato</th>
                    <th>Lote</th>
                    <th>Cessionário</th>
                    <th className="num">Documentos</th>
                    <th className="num">Refugados</th>
                  </tr>
                </thead>
                <tbody>
                  {resultados.map((r) => (
                    <tr
                      key={r.id}
                      className="clickable"
                      onClick={() => navigate(`/registros/${r.id}`)}
                    >
                      <td className="num">{r.id}</td>
                      <td className="num">{r.contrato ?? "—"}</td>
                      <td>{r.lote ?? "—"}</td>
                      <td>{r.cessionario?.nome_cessionario ?? <span className="muted">—</span>}</td>
                      <td className="num">{r.qtde_documentos}</td>
                      <td className="num">
                        {r.qtde_refugados > 0 ? (
                          <span className="pill crit">{r.qtde_refugados}</span>
                        ) : (
                          0
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </>
  );
}
