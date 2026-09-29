import { Fragment, useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, API_BASE, ApiError, jsonBody, tokens } from "../api/client";
import type {
  AssinaturasResumo,
  Certificado,
  Documento,
  Motivo,
  RegistroBusca,
  TipoDocumento,
} from "../api/types";

export function RegistroPage() {
  const { id } = useParams();
  const registroId = Number(id);
  const [registro, setRegistro] = useState<RegistroBusca | null>(null);
  const [docs, setDocs] = useState<Documento[]>([]);
  const [tipos, setTipos] = useState<TipoDocumento[]>([]);
  const [motivos, setMotivos] = useState<Motivo[]>([]);
  const [certificados, setCertificados] = useState<Certificado[]>([]);
  const [selecionado, setSelecionado] = useState<number | null>(null);
  const [erro, setErro] = useState("");

  const carregarDocs = useCallback(async () => {
    setDocs(await api<Documento[]>(`/registros/${registroId}/documentos`));
  }, [registroId]);

  useEffect(() => {
    (async () => {
      setErro("");
      try {
        const [regs, td, mo, cert] = await Promise.all([
          api<RegistroBusca[]>(`/registros?registro_id=${registroId}`),
          api<TipoDocumento[]>("/tipos-documento"),
          api<Motivo[]>("/motivos"),
          api<Certificado[]>("/certificados"),
        ]);
        setRegistro(regs[0] ?? null);
        setTipos(td);
        setMotivos(mo);
        setCertificados(cert);
        await carregarDocs();
      } catch (err) {
        setErro(err instanceof ApiError ? err.detail : "Falha ao carregar o registro");
      }
    })();
  }, [registroId, carregarDocs]);

  return (
    <>
      <div className="toolbar">
        <Link to="/" className="btn ghost sm">
          ← Consulta
        </Link>
      </div>

      <div className="page-head">
        <p className="eyebrow">Registro nº {registroId}</p>
        <h1>{registro?.cessionario?.nome_cessionario ?? `Contrato ${registro?.contrato ?? "—"}`}</h1>
        <p className="muted">
          Lote {registro?.lote ?? "—"} · Contrato {registro?.contrato ?? "—"} ·{" "}
          {docs.length} documento(s)
          {registro && registro.qtde_refugados > 0 ? ` · ${registro.qtde_refugados} refugado(s)` : ""}
        </p>
      </div>

      {erro && <div className="alert err">{erro}</div>}

      <AnexarForm tipos={tipos} registroId={registroId} onCriado={carregarDocs} />

      <div className="card" style={{ padding: 0, marginTop: "1.2rem" }}>
        {docs.length === 0 ? (
          <p className="empty">Nenhum documento anexado. Use “Anexar documento” acima.</p>
        ) : (
          <div className="tablewrap" style={{ border: "none" }}>
            <table>
              <thead>
                <tr>
                  <th>Documento</th>
                  <th>Folha</th>
                  <th>F/V</th>
                  <th>Situação</th>
                  <th className="num">Assinaturas</th>
                  <th className="num">Comentários</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {docs.map((d) => (
                  <Fragment key={d.id}>
                    <tr>
                      <td>{d.tipo_descricao ?? <span className="muted">sem tipo</span>}</td>
                      <td className="num">
                        {d.nr_folha ?? "—"}
                        {d.total_folhas ? `/${d.total_folhas}` : ""}
                      </td>
                      <td>{d.face ?? "—"}</td>
                      <td>
                        {d.refugada ? (
                          <span className="pill crit">refugada</span>
                        ) : (
                          <span className="pill accent">ok</span>
                        )}
                      </td>
                      <td className="num">
                        {d.qtde_assinaturas > 0 ? (
                          <span className="pill accent">{d.qtde_assinaturas} assinatura(s)</span>
                        ) : (
                          0
                        )}
                      </td>
                      <td className="num">{d.qtde_comentarios}</td>
                      <td>
                        <button
                          className="btn soft sm"
                          onClick={() => setSelecionado(selecionado === d.id ? null : d.id)}
                        >
                          {selecionado === d.id ? "Fechar" : "Ações"}
                        </button>
                      </td>
                    </tr>
                    {selecionado === d.id && (
                      <tr>
                        <td colSpan={7} style={{ padding: 0 }}>
                          <DocumentoAcoes
                            doc={d}
                            motivos={motivos}
                            certificados={certificados}
                            onMudou={carregarDocs}
                          />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

function AnexarForm({
  tipos,
  registroId,
  onCriado,
}: {
  tipos: TipoDocumento[];
  registroId: number;
  onCriado: () => Promise<void>;
}) {
  const [tipoId, setTipoId] = useState("");
  const [folha, setFolha] = useState("1");
  const [total, setTotal] = useState("1");
  const [face, setFace] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function anexar(e: React.FormEvent) {
    e.preventDefault();
    setMsg("");
    setBusy(true);
    try {
      await api(
        `/registros/${registroId}/documentos`,
        jsonBody({
          tipo_doc_id: tipoId ? Number(tipoId) : null,
          nr_folha: folha ? Number(folha) : null,
          total_folhas: total ? Number(total) : null,
          face: face || null,
        }),
      );
      await onCriado();
      setMsg("Documento anexado.");
    } catch (err) {
      setMsg(err instanceof ApiError ? err.detail : "Falha ao anexar");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>Anexar documento</h2>
      <form className="row" onSubmit={anexar}>
        <div className="field" style={{ flex: 2 }}>
          <label>Tipo de documento</label>
          <select value={tipoId} onChange={(e) => setTipoId(e.target.value)}>
            <option value="">— selecione —</option>
            {tipos
              .filter((t) => t.ativo)
              .map((t) => (
                <option key={t.id} value={t.id}>
                  {t.descricao}
                </option>
              ))}
          </select>
        </div>
        <div className="field">
          <label>Folha</label>
          <input className="num" value={folha} onChange={(e) => setFolha(e.target.value)} />
        </div>
        <div className="field">
          <label>Total</label>
          <input className="num" value={total} onChange={(e) => setTotal(e.target.value)} />
        </div>
        <div className="field">
          <label>Frente/Verso</label>
          <select value={face} onChange={(e) => setFace(e.target.value)}>
            <option value="">—</option>
            <option value="F">Frente</option>
            <option value="V">Verso</option>
          </select>
        </div>
        <button className="btn" disabled={busy}>
          {busy ? "…" : "Anexar"}
        </button>
      </form>
      {msg && <div className="alert ok">{msg}</div>}
    </div>
  );
}

function DocumentoAcoes({
  doc,
  motivos,
  certificados,
  onMudou,
}: {
  doc: Documento;
  motivos: Motivo[];
  certificados: Certificado[];
  onMudou: () => Promise<void>;
}) {
  const [msg, setMsg] = useState<{ t: "ok" | "err"; s: string } | null>(null);
  const [resumo, setResumo] = useState<AssinaturasResumo | null>(null);

  // comentário/refugo
  const [motivoId, setMotivoId] = useState("");
  const [comentario, setComentario] = useState("");
  const [refugar, setRefugar] = useState(false);
  // assinar
  const [certId, setCertId] = useState(certificados[0]?.id ? String(certificados[0].id) : "");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  async function comFeedback(fn: () => Promise<void>, ok: string) {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      setMsg({ t: "ok", s: ok });
      await onMudou();
    } catch (err) {
      setMsg({ t: "err", s: err instanceof ApiError ? err.detail : "Falha na operação" });
    } finally {
      setBusy(false);
    }
  }

  async function enviarArquivo() {
    if (!arquivo) return;
    const fd = new FormData();
    fd.append("file", arquivo);
    await comFeedback(
      () => api(`/documentos/${doc.id}/arquivo`, { method: "POST", body: fd }),
      "Arquivo enviado.",
    );
  }

  async function salvarComentario() {
    await comFeedback(
      () =>
        api(
          `/documentos/${doc.id}/comentario`,
          jsonBody({
            motivo_id: motivoId ? Number(motivoId) : null,
            comentario: comentario || null,
            refugar,
          }),
        ),
      refugar ? "Documento refugado." : "Comentário adicionado.",
    );
  }

  async function assinar() {
    await comFeedback(
      () => api(`/documentos/${doc.id}/assinar`, jsonBody({ certificado_id: Number(certId) })),
      "Documento assinado.",
    );
  }

  async function verAssinaturas() {
    setMsg(null);
    try {
      setResumo(await api<AssinaturasResumo>(`/documentos/${doc.id}/assinaturas`));
    } catch (err) {
      setMsg({ t: "err", s: err instanceof ApiError ? err.detail : "Falha" });
    }
  }

  async function baixarAssinado() {
    try {
      const res = await fetch(`${API_BASE}/documentos/${doc.id}/assinado`, {
        headers: { Authorization: `Bearer ${tokens.access ?? ""}` },
      });
      if (!res.ok) throw new Error();
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = `documento_${doc.id}_assinado.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setMsg({ t: "err", s: "Documento ainda não possui versão assinada." });
    }
  }

  return (
    <div className="drawer">
      {msg && <div className={`alert ${msg.t === "ok" ? "ok" : "err"}`}>{msg.s}</div>}
      <div className="drawer-grid">
        <section>
          <h3>Enviar imagem/arquivo</h3>
          <div className="stack">
            <input type="file" onChange={(e) => setArquivo(e.target.files?.[0] ?? null)} />
            <button className="btn sm" disabled={busy || !arquivo} onClick={enviarArquivo}>
              Enviar arquivo
            </button>
          </div>
        </section>

        <section>
          <h3>Comentário / Refugo</h3>
          <div className="stack">
            <select value={motivoId} onChange={(e) => setMotivoId(e.target.value)}>
              <option value="">— motivo (opcional) —</option>
              {motivos.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.descricao}
                </option>
              ))}
            </select>
            <input
              placeholder="Comentário / particularidade"
              value={comentario}
              onChange={(e) => setComentario(e.target.value)}
            />
            <label style={{ display: "flex", gap: ".4rem", alignItems: "center" }}>
              <input
                type="checkbox"
                style={{ width: "auto" }}
                checked={refugar}
                onChange={(e) => setRefugar(e.target.checked)}
              />
              Marcar como refugado
            </label>
            <button className="btn sm" disabled={busy} onClick={salvarComentario}>
              Salvar
            </button>
          </div>
        </section>

        <section>
          <h3>Assinar (A1)</h3>
          {certificados.length === 0 ? (
            <p className="hint">
              Nenhum certificado. Adicione em <Link to="/certificados">Certificados</Link>.
            </p>
          ) : (
            <div className="stack">
              <select value={certId} onChange={(e) => setCertId(e.target.value)}>
                {certificados.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nome_titular ?? `Certificado ${c.id}`}
                  </option>
                ))}
              </select>
              <button className="btn sm" disabled={busy || !certId} onClick={assinar}>
                Assinar documento
              </button>
            </div>
          )}
        </section>

        <section>
          <h3>Assinaturas</h3>
          <div className="stack">
            <div style={{ display: "flex", gap: ".5rem" }}>
              <button className="btn ghost sm" onClick={verAssinaturas}>
                Ver ({doc.qtde_assinaturas})
              </button>
              <button className="btn ghost sm" onClick={baixarAssinado}>
                Baixar PDF
              </button>
            </div>
            {resumo && (
              <div className="hint">
                {resumo.qtde_assinaturas} assinatura(s)
                {resumo.assinaturas_no_pdf != null ? ` · ${resumo.assinaturas_no_pdf} no PDF` : ""}
                <ul style={{ margin: ".4rem 0 0", paddingLeft: "1rem" }}>
                  {resumo.assinaturas.map((a) => (
                    <li key={a.ordem}>
                      #{a.ordem} {a.titular ?? ""}
                      {a.carimbo_nova_folha ? " (nova folha)" : ""} — {a.status}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
