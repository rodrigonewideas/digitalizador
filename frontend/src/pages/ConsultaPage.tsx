import { useCallback, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../api/client";
import type { RegistroBusca } from "../api/types";
import { VisualizadorUnificado } from "../components/VisualizadorUnificado";

type TipoBusca = "lote" | "cessionario" | "contrato" | "registro_id";

const ROTULOS: Record<TipoBusca, { rotulo: string; dica: string }> = {
  lote: { rotulo: "Nº do lote (terreno)", dica: "ex.: 1588" },
  cessionario: { rotulo: "Nome do cessionário", dica: "ao menos 3 letras" },
  contrato: { rotulo: "Contrato (nº interno)", dica: "ex.: 6016" },
  registro_id: { rotulo: "Nº do registro", dica: "ex.: 13291" },
};

export function ConsultaPage() {
  const [tipo, setTipo] = useState<TipoBusca>("lote");
  const [valor, setValor] = useState("");
  const [resultados, setResultados] = useState<RegistroBusca[] | null>(null);
  const [marcados, setMarcados] = useState<Set<number>>(new Set());
  const [erro, setErro] = useState("");
  const [busy, setBusy] = useState(false);
  const [buscaAberta, setBuscaAberta] = useState(false);
  const [ultimaBusca, setUltimaBusca] = useState("");

  async function buscar(e?: React.FormEvent) {
    e?.preventDefault();
    const v = valor.trim();
    if (!v) {
      setErro("Informe um valor para a busca.");
      return;
    }
    setErro("");
    setBusy(true);
    try {
      const params = new URLSearchParams({ [tipo]: v });
      const r = await api<RegistroBusca[]>(`/registros?${params.toString()}`);
      setResultados(r);
      setUltimaBusca(`${ROTULOS[tipo].rotulo}: ${v}`);
      // pré-seleciona tudo quando o resultado é pequeno (fluxo mais comum)
      setMarcados(new Set(r.length <= 5 ? r.map((x) => x.id) : []));
      setBuscaAberta(false);
    } catch (err) {
      setErro(err instanceof ApiError ? err.detail : "Falha na busca");
    } finally {
      setBusy(false);
    }
  }

  const registrosMarcados = (resultados ?? []).filter((r) => marcados.has(r.id));

  const formBusca = (
    <form className="row" onSubmit={buscar}>
      <div className="field" style={{ maxWidth: "14rem" }}>
        <label htmlFor="tipo">Tipo de busca</label>
        <select id="tipo" value={tipo} onChange={(e) => setTipo(e.target.value as TipoBusca)}>
          <option value="lote">Nº do lote</option>
          <option value="cessionario">Nome do cessionário</option>
          <option value="contrato">Contrato</option>
          <option value="registro_id">Nº do registro</option>
        </select>
      </div>
      <div className="field" style={{ flex: 2 }}>
        <label htmlFor="valor">{ROTULOS[tipo].rotulo}</label>
        <input
          id="valor"
          value={valor}
          placeholder={ROTULOS[tipo].dica}
          autoFocus
          onChange={(e) => setValor(e.target.value)}
        />
      </div>
      <button className="btn" disabled={busy}>
        {busy ? "Buscando…" : "Filtrar"}
      </button>
    </form>
  );

  // ---- estado 1: sem resultados ainda — busca centrada
  if (resultados === null) {
    return (
      <>
        <div className="page-head">
          <p className="eyebrow">Painel de manipulação</p>
          <h1>Consulta de documentos</h1>
          <p className="muted">
            Busque por lote (terreno), nome do cessionário, contrato ou nº do registro.
          </p>
        </div>
        <div className="card">{formBusca}{erro && <div className="alert err">{erro}</div>}</div>
      </>
    );
  }

  // ---- estado 2: split-screen resultados + visualizador
  return (
    <div className="consulta-split">
      <div className="split-cab">
        <strong>{ultimaBusca}</strong>
        <span className="muted">({resultados.length} registro(s))</span>
        <span className="spacer" />
        <button className="btn ghost sm" type="button" onClick={() => setBuscaAberta((a) => !a)}>
          🔍 Novo filtro
        </button>
      </div>
      {buscaAberta && (
        <div className="card" style={{ marginBottom: ".8rem" }}>
          {formBusca}
          {erro && <div className="alert err">{erro}</div>}
        </div>
      )}

      {resultados.length === 0 ? (
        <div className="card">
          <p className="empty">Nenhum registro encontrado para o filtro.</p>
        </div>
      ) : (
        <SplitPane
          esquerda={
            <div className="tabela-registros">
              <table>
                <thead>
                  <tr>
                    <th>
                      <input
                        type="checkbox"
                        checked={marcados.size === resultados.length}
                        onChange={(e) =>
                          setMarcados(
                            e.target.checked ? new Set(resultados.map((r) => r.id)) : new Set(),
                          )
                        }
                      />
                    </th>
                    <th>Contrato</th>
                    <th>Cessionário</th>
                    <th>Venda</th>
                    <th>Terreno</th>
                    <th className="num">Docs</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {resultados.map((r) => (
                    <tr
                      key={r.id}
                      className={marcados.has(r.id) ? "sel" : ""}
                      onClick={() =>
                        setMarcados((prev) => {
                          const s = new Set(prev);
                          if (s.has(r.id)) s.delete(r.id);
                          else s.add(r.id);
                          return s;
                        })
                      }
                    >
                      <td onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={marcados.has(r.id)}
                          onChange={(e) =>
                            setMarcados((prev) => {
                              const s = new Set(prev);
                              if (e.target.checked) s.add(r.id);
                              else s.delete(r.id);
                              return s;
                            })
                          }
                        />
                      </td>
                      <td>{r.cessionario?.nr_contrato ?? r.contrato ?? "—"}</td>
                      <td className="cell-nome" title={r.cessionario?.cessionarios?.join(", ")}>
                        {r.cessionario?.nome_cessionario ?? "—"}
                      </td>
                      <td>{r.cessionario?.dt_venda ?? "—"}</td>
                      <td>
                        {r.cessionario?.nr_terreno
                          ? `${r.cessionario.tipo_terreno ?? ""} ${r.cessionario.nr_terreno}`.trim()
                          : (r.lote ?? "—")}
                      </td>
                      <td className="num">{r.qtde_documentos}</td>
                      <td onClick={(e) => e.stopPropagation()}>
                        <Link
                          to={`/registros/${r.id}`}
                          className="btn ghost sm"
                          title="Abrir registro (anexar/assinar)"
                        >
                          ↗
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          }
          direita={<VisualizadorUnificado registros={registrosMarcados} />}
        />
      )}
    </div>
  );
}

/** Split horizontal com divisor arrastável (largura persistida). */
function SplitPane({ esquerda, direita }: { esquerda: React.ReactNode; direita: React.ReactNode }) {
  const [pct, setPct] = useState(() => Number(localStorage.getItem("dig.split") ?? 30));
  const ref = useRef<HTMLDivElement>(null);

  const arrastar = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const caixa = ref.current?.getBoundingClientRect();
    if (!caixa) return;
    const box = caixa;
    function mover(ev: MouseEvent) {
      const p = Math.min(60, Math.max(16, ((ev.clientX - box.left) / box.width) * 100));
      setPct(p);
      localStorage.setItem("dig.split", String(Math.round(p)));
    }
    function soltar() {
      window.removeEventListener("mousemove", mover);
      window.removeEventListener("mouseup", soltar);
    }
    window.addEventListener("mousemove", mover);
    window.addEventListener("mouseup", soltar);
  }, []);

  return (
    <div className="split" ref={ref}>
      <div className="split-esq" style={{ width: `${pct}%` }}>
        {esquerda}
      </div>
      <div className="split-div" onMouseDown={arrastar} title="Arraste para redimensionar" />
      <div className="split-dir">{direita}</div>
    </div>
  );
}
