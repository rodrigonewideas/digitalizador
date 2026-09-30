import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import type { Documento, RegistroBusca } from "../api/types";
import {
  abrirSelecionadosEmGuia,
  baixarComoZip,
  buscarImagemBlob,
  type DocComRegistro,
  nomeArquivoDoc,
  salvarBlob,
} from "../utils/download";
import { ThumbDocumento, useImagemDocumento } from "./ImagemDoc";
import { Modal } from "./Modal";

/** Painel direito da Consulta: documentos de TODOS os registros selecionados. */
export function VisualizadorUnificado({ registros }: { registros: RegistroBusca[] }) {
  const [docs, setDocs] = useState<DocComRegistro[]>([]);
  const [carregando, setCarregando] = useState(false);
  const [tipo, setTipo] = useState("todos");
  const [modo, setModo] = useState<"galeria" | "lista">("galeria");
  const [marcados, setMarcados] = useState<Set<number>>(new Set());
  const [visor, setVisor] = useState<number | null>(null); // índice no array filtrado
  const [msg, setMsg] = useState("");

  useEffect(() => {
    let vivo = true;
    (async () => {
      if (registros.length === 0) {
        setDocs([]);
        setMarcados(new Set());
        return;
      }
      setCarregando(true);
      try {
        const todos: DocComRegistro[] = [];
        for (const r of registros) {
          const dd = await api<Documento[]>(`/registros/${r.id}/documentos`);
          todos.push(...dd.map((d) => ({ ...d, registro: r })));
        }
        if (vivo) setDocs(todos);
      } finally {
        if (vivo) setCarregando(false);
      }
    })();
    return () => {
      vivo = false;
    };
  }, [registros]);

  const tipos = useMemo(
    () => [...new Set(docs.map((d) => d.tipo_descricao ?? "Documento"))].sort(),
    [docs],
  );
  const filtrados = useMemo(
    () => (tipo === "todos" ? docs : docs.filter((d) => (d.tipo_descricao ?? "Documento") === tipo)),
    [docs, tipo],
  );
  const selecionados = filtrados.filter((d) => marcados.has(d.id));
  const todosMarcados = filtrados.length > 0 && filtrados.every((d) => marcados.has(d.id));

  function marcar(id: number, on: boolean) {
    setMarcados((prev) => {
      const s = new Set(prev);
      if (on) s.add(id);
      else s.delete(id);
      return s;
    });
  }

  async function baixarSelecionados() {
    if (selecionados.length === 0) return;
    setMsg(`Preparando ZIP (0/${selecionados.length})…`);
    const { ok, falhas } = await baixarComoZip(selecionados, (f, t) =>
      setMsg(`Preparando ZIP (${f}/${t})…`),
    );
    setMsg(falhas ? `ZIP com ${ok} imagem(ns); ${falhas} sem imagem no storage.` : "");
  }

  if (registros.length === 0) {
    return (
      <div className="visor-vazio">
        <p className="empty">Marque um ou mais registros à esquerda para ver os documentos.</p>
      </div>
    );
  }

  return (
    <div className="visor">
      <div className="visor-topo">
        <div className="field" style={{ minWidth: "12rem" }}>
          <label>Tipo de documento</label>
          <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
            <option value="todos">Todos ({docs.length})</option>
            {tipos.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <label className="check-row" style={{ alignSelf: "end" }}>
          <input
            type="checkbox"
            checked={todosMarcados}
            onChange={(e) =>
              setMarcados(e.target.checked ? new Set(filtrados.map((d) => d.id)) : new Set())
            }
          />
          Selecionar todos ({filtrados.length})
        </label>
        <span className="spacer" />
        <div className="visor-modos">
          <button
            type="button"
            className={`btn sm ${modo === "galeria" ? "" : "ghost"}`}
            onClick={() => setModo("galeria")}
            title="Galeria"
          >
            ⊞
          </button>
          <button
            type="button"
            className={`btn sm ${modo === "lista" ? "" : "ghost"}`}
            onClick={() => setModo("lista")}
            title="Lista"
          >
            ☰
          </button>
        </div>
      </div>

      {selecionados.length > 0 && (
        <div className="visor-acoes">
          <span className="pill accent">{selecionados.length} selecionado(s)</span>
          <button className="btn sm" type="button" onClick={baixarSelecionados}>
            ⬇ Baixar ZIP
          </button>
          <button
            className="btn soft sm"
            type="button"
            onClick={async () => {
              const ok = await abrirSelecionadosEmGuia(selecionados);
              setMsg(ok ? "" : "O navegador bloqueou a nova guia — permita pop-ups para este site.");
            }}
          >
            ↗ Abrir/Imprimir
          </button>
          <button className="btn ghost sm" type="button" onClick={() => setMarcados(new Set())}>
            Limpar
          </button>
        </div>
      )}
      {msg && <div className="alert ok" style={{ margin: ".6rem 0 0" }}>{msg}</div>}

      <div className="visor-corpo">
        {carregando ? (
          <p className="empty">Carregando documentos…</p>
        ) : filtrados.length === 0 ? (
          <p className="empty">Nenhum documento {tipo !== "todos" ? `do tipo "${tipo}"` : ""}.</p>
        ) : modo === "galeria" ? (
          <div className="galeria">
            {filtrados.map((d, i) => (
              <div key={d.id} className={`doc-card${marcados.has(d.id) ? " sel" : ""}`}>
                <label className="doc-card-topo">
                  <input
                    type="checkbox"
                    checked={marcados.has(d.id)}
                    onChange={(e) => marcar(d.id, e.target.checked)}
                  />
                  <span className="muted">nº {d.id}</span>
                  {d.refugada && <span className="pill crit">refugada</span>}
                  {d.qtde_assinaturas > 0 && (
                    <span className="pill accent">{d.qtde_assinaturas}✍</span>
                  )}
                </label>
                <div className="doc-card-img" onClick={() => setVisor(i)}>
                  <ThumbDocumento docId={d.id} altura={150} />
                </div>
                <div className="doc-card-info">
                  <strong>{d.tipo_descricao ?? "Documento"}</strong>
                  <span className="muted">
                    {d.registro.cessionario?.nr_contrato ?? d.registro.contrato ?? "—"} ·{" "}
                    pg {d.nr_folha ?? "?"}
                    {d.total_folhas ? `/${d.total_folhas}` : ""}
                    {d.face ? ` · ${d.face === "F" ? "frente" : "verso"}` : ""}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <table className="lista-docs">
            <thead>
              <tr>
                <th />
                <th>Documento</th>
                <th>Contrato</th>
                <th>Folha</th>
                <th>F/V</th>
                <th>Situação</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filtrados.map((d, i) => (
                <tr key={d.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={marcados.has(d.id)}
                      onChange={(e) => marcar(d.id, e.target.checked)}
                    />
                  </td>
                  <td>{d.tipo_descricao ?? "Documento"}</td>
                  <td>{d.registro.cessionario?.nr_contrato ?? d.registro.contrato ?? "—"}</td>
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
                  <td>
                    <button className="btn soft sm" type="button" onClick={() => setVisor(i)}>
                      Ver
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {visor != null && filtrados[visor] && (
        <VisorModal
          docs={filtrados}
          indice={visor}
          onNavegar={setVisor}
          onClose={() => setVisor(null)}
        />
      )}
    </div>
  );
}

/** Modal de visualização: imagem grande, zoom, ←/→, baixar, metadados. */
function VisorModal({
  docs,
  indice,
  onNavegar,
  onClose,
}: {
  docs: DocComRegistro[];
  indice: number;
  onNavegar: (i: number) => void;
  onClose: () => void;
}) {
  const d = docs[indice];
  const { url, falhou } = useImagemDocumento(d.id, "full");
  const [zoom, setZoom] = useState(false);

  useEffect(() => setZoom(false), [indice]);

  useEffect(() => {
    function tecla(e: KeyboardEvent) {
      if (e.key === "ArrowRight" && indice < docs.length - 1) onNavegar(indice + 1);
      if (e.key === "ArrowLeft" && indice > 0) onNavegar(indice - 1);
    }
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [indice, docs.length, onNavegar]);

  async function baixar() {
    try {
      salvarBlob(nomeArquivoDoc(d), await buscarImagemBlob(d.id, "full"));
    } catch {
      /* sem imagem */
    }
  }

  return (
    <Modal
      titulo={`${d.tipo_descricao ?? "Documento"} · nº ${d.id} (${indice + 1}/${docs.length})`}
      onClose={onClose}
      largura="min(94vw, 74rem)"
    >
      <div className="visor-nav">
        <button
          className="btn ghost sm"
          type="button"
          disabled={indice === 0}
          onClick={() => onNavegar(indice - 1)}
        >
          ← Anterior
        </button>
        <span className="muted" style={{ fontSize: ".85rem" }}>
          {d.registro.cessionario?.nome_cessionario ?? ""} · contrato{" "}
          {d.registro.cessionario?.nr_contrato ?? d.registro.contrato ?? "—"} · pg{" "}
          {d.nr_folha ?? "?"}
          {d.total_folhas ? `/${d.total_folhas}` : ""}
          {d.face ? ` · ${d.face === "F" ? "frente" : "verso"}` : ""}
          {d.registro.cessionario?.vendedor ? ` · vendedor: ${d.registro.cessionario.vendedor}` : ""}
        </span>
        <span className="spacer" />
        <button className="btn soft sm" type="button" onClick={() => setZoom((z) => !z)}>
          {zoom ? "Ajustar" : "Zoom"}
        </button>
        <button className="btn sm" type="button" onClick={baixar}>
          ⬇ Baixar
        </button>
        <Link className="btn ghost sm" to={`/registros/${d.registro.id}`}>
          Abrir registro
        </Link>
        <button
          className="btn ghost sm"
          type="button"
          disabled={indice === docs.length - 1}
          onClick={() => onNavegar(indice + 1)}
        >
          Próxima →
        </button>
      </div>
      <div className={`visor-palco${zoom ? " zoom" : ""}`}>
        {falhou ? (
          <p className="empty">Imagem ainda não disponível no storage.</p>
        ) : url ? (
          <img src={url} alt={`Documento ${d.id}`} onClick={() => setZoom((z) => !z)} />
        ) : (
          <p className="muted" style={{ padding: "6rem 0" }}>Carregando…</p>
        )}
      </div>
    </Modal>
  );
}
