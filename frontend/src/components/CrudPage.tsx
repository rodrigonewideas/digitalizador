import { Fragment, useCallback, useEffect, useState } from "react";

import { api, ApiError, jsonBody } from "../api/client";
import { ConfirmDialog, Modal } from "./Modal";

export interface CrudColuna {
  key: string;
  label: string;
  tipo?: "bool" | "ativo" | "num" | "text" | "data";
}
export interface CrudCampo {
  key: string;
  label: string;
  tipo: "text" | "number" | "checkbox";
  obrigatorio?: boolean;
  padrao?: string | number | boolean;
  full?: boolean;
}
export interface CrudFiltro {
  campo: string;
  label: string;
  tipo: "texto" | "ativo" | "data";
}

type Registro = Record<string, any>;

export function CrudPage({
  eyebrow = "Tabelas",
  titulo,
  singular,
  descricao,
  endpoint,
  colunas,
  campos,
  filtros,
  idKey = "id",
}: {
  eyebrow?: string;
  titulo: string;
  singular?: string;
  descricao?: string;
  endpoint: string;
  colunas: CrudColuna[];
  campos: CrudCampo[];
  filtros?: CrudFiltro[];
  idKey?: string;
}) {
  const nomeSingular = singular ?? titulo;
  const colRotulo =
    colunas.find((c) => c.key !== idKey && !["num", "ativo", "bool"].includes(c.tipo ?? "")) ??
    colunas[0];

  const [lista, setLista] = useState<Registro[]>([]);
  const [fvals, setFvals] = useState<Record<string, string>>({});
  const [form, setForm] = useState<Registro | null>(null);
  const [editId, setEditId] = useState<number | null>(null);
  const [excluindo, setExcluindo] = useState<Registro | null>(null);
  const [msg, setMsg] = useState<{ t: "ok" | "err"; s: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const carregar = useCallback(async () => {
    try {
      setLista(await api<Registro[]>(endpoint));
    } catch (e) {
      setMsg({ t: "err", s: e instanceof ApiError ? e.detail : "Falha ao carregar" });
    }
  }, [endpoint]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  const listaFiltrada = lista.filter((item) =>
    (filtros ?? []).every((f) => {
      const v = fvals[f.campo];
      if (f.tipo === "texto") {
        if (!v) return true;
        return String(item[f.campo] ?? "").toLowerCase().includes(v.toLowerCase());
      }
      if (f.tipo === "ativo") {
        if (!v) return true;
        return !!item[f.campo] === (v === "ativo");
      }
      if (f.tipo === "data") {
        const de = fvals[`${f.campo}_de`];
        const ate = fvals[`${f.campo}_ate`];
        const d = item[f.campo] ? String(item[f.campo]).slice(0, 10) : "";
        if (de && (!d || d < de)) return false;
        if (ate && (!d || d > ate)) return false;
        return true;
      }
      return true;
    }),
  );

  function novo() {
    const inicial: Registro = {};
    campos.forEach((c) => {
      inicial[c.key] = c.padrao ?? (c.tipo === "checkbox" ? true : "");
    });
    setForm(inicial);
    setEditId(null);
    setMsg(null);
  }

  function editar(r: Registro) {
    const f: Registro = {};
    campos.forEach((c) => {
      f[c.key] = r[c.key] ?? (c.tipo === "checkbox" ? false : "");
    });
    setForm(f);
    setEditId(r[idKey]);
    setMsg(null);
  }

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setBusy(true);
    setMsg(null);
    const payload: Registro = {};
    campos.forEach((c) => {
      let v = form[c.key];
      if (c.tipo === "number") v = v === "" || v == null ? null : Number(v);
      payload[c.key] = v;
    });
    try {
      if (editId == null) {
        await api(endpoint, jsonBody(payload));
      } else {
        await api(`${endpoint}/${editId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      }
      setForm(null);
      setEditId(null);
      await carregar();
      setMsg({ t: "ok", s: editId == null ? "Registro criado." : "Registro atualizado." });
    } catch (err) {
      setMsg({ t: "err", s: err instanceof ApiError ? err.detail : "Falha ao salvar" });
    } finally {
      setBusy(false);
    }
  }

  async function confirmarExclusao() {
    if (!excluindo) return;
    setBusy(true);
    setMsg(null);
    try {
      await api(`${endpoint}/${excluindo[idKey]}`, { method: "DELETE" });
      setExcluindo(null);
      await carregar();
      setMsg({ t: "ok", s: "Registro excluído." });
    } catch (err) {
      setExcluindo(null);
      setMsg({ t: "err", s: err instanceof ApiError ? err.detail : "Falha ao excluir" });
    } finally {
      setBusy(false);
    }
  }

  function valor(r: Registro, col: CrudColuna) {
    const v = r[col.key];
    if (col.tipo === "bool") return v ? "Sim" : "Não";
    if (col.tipo === "data") return v ? String(v).slice(0, 10).split("-").reverse().join("/") : "—";
    if (col.tipo === "ativo")
      return <span className={`pill ${v ? "accent" : "crit"}`}>{v ? "ativo" : "inativo"}</span>;
    return v ?? "—";
  }

  const filtrando = listaFiltrada.length !== lista.length;

  return (
    <>
      <div className="page-head">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{titulo}</h1>
        {descricao && <p className="muted">{descricao}</p>}
      </div>

      {msg && <div className={`alert ${msg.t === "ok" ? "ok" : "err"}`}>{msg.s}</div>}

      {filtros && filtros.length > 0 && (
        <div className="card filtros">
          {filtros.map((f) =>
            f.tipo === "data" ? (
              <Fragment key={f.campo}>
                <div className="field">
                  <label>{f.label} de</label>
                  <input
                    type="date"
                    value={fvals[`${f.campo}_de`] ?? ""}
                    onChange={(e) => setFvals({ ...fvals, [`${f.campo}_de`]: e.target.value })}
                  />
                </div>
                <div className="field">
                  <label>{f.label} até</label>
                  <input
                    type="date"
                    value={fvals[`${f.campo}_ate`] ?? ""}
                    onChange={(e) => setFvals({ ...fvals, [`${f.campo}_ate`]: e.target.value })}
                  />
                </div>
              </Fragment>
            ) : (
              <div className="field" key={f.campo}>
                <label>{f.label}</label>
                {f.tipo === "ativo" ? (
                  <select value={fvals[f.campo] ?? ""} onChange={(e) => setFvals({ ...fvals, [f.campo]: e.target.value })}>
                    <option value="">Todos</option>
                    <option value="ativo">Ativos</option>
                    <option value="inativo">Inativos</option>
                  </select>
                ) : (
                  <input
                    value={fvals[f.campo] ?? ""}
                    placeholder="Buscar…"
                    onChange={(e) => setFvals({ ...fvals, [f.campo]: e.target.value })}
                  />
                )}
              </div>
            ),
          )}
          <button className="btn ghost sm" type="button" onClick={() => setFvals({})}>
            Limpar
          </button>
        </div>
      )}

      <div className="toolbar">
        <button className="btn" onClick={novo}>
          + Novo
        </button>
        <span className="spacer" />
        <span className="muted">
          {listaFiltrada.length}
          {filtrando ? ` de ${lista.length}` : ""} registro(s)
        </span>
      </div>

      <div className="card" style={{ padding: 0 }}>
        {listaFiltrada.length === 0 ? (
          <p className="empty">{lista.length === 0 ? "Nenhum registro." : "Nenhum registro para o filtro."}</p>
        ) : (
          <div className="tablewrap" style={{ border: "none" }}>
            <table>
              <thead>
                <tr>
                  {colunas.map((c) => (
                    <th key={c.key} className={c.tipo === "num" ? "num" : undefined}>
                      {c.label}
                    </th>
                  ))}
                  <th />
                </tr>
              </thead>
              <tbody>
                {listaFiltrada.map((r) => (
                  <tr key={r[idKey]}>
                    {colunas.map((c) => (
                      <td key={c.key} className={c.tipo === "num" ? "num" : undefined}>
                        {valor(r, c)}
                      </td>
                    ))}
                    <td style={{ whiteSpace: "nowrap", textAlign: "right" }}>
                      <button className="btn soft sm" onClick={() => editar(r)}>
                        Editar
                      </button>{" "}
                      <button className="btn danger sm" onClick={() => setExcluindo(r)}>
                        Excluir
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {form && (
        <Modal
          titulo={editId == null ? `Novo — ${nomeSingular}` : `Editar ${nomeSingular} #${editId}`}
          onClose={() => setForm(null)}
          largura={campos.length > 3 ? "44rem" : "30rem"}
        >
          <form onSubmit={salvar}>
            <div className="form-grid">
              {campos.map((c, i) => (
                <div className={`field${c.full ? " full" : ""}`} key={c.key}>
                  <label>{c.label}</label>
                  {c.tipo === "checkbox" ? (
                    <label className="check-row">
                      <input
                        type="checkbox"
                        checked={!!form[c.key]}
                        onChange={(e) => setForm({ ...form, [c.key]: e.target.checked })}
                      />
                      Sim
                    </label>
                  ) : (
                    <input
                      type={c.tipo === "number" ? "number" : "text"}
                      value={form[c.key] ?? ""}
                      required={c.obrigatorio}
                      autoFocus={i === 0}
                      onChange={(e) => setForm({ ...form, [c.key]: e.target.value })}
                    />
                  )}
                </div>
              ))}
            </div>
            <div className="modal-foot">
              <button type="button" className="btn ghost" onClick={() => setForm(null)}>
                Cancelar
              </button>
              <button className="btn" disabled={busy}>
                {busy ? "Salvando…" : "Salvar"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {excluindo && (
        <ConfirmDialog
          titulo="Excluir registro"
          mensagem={
            <>
              Tem certeza que deseja excluir <strong>{excluindo[colRotulo.key] ?? excluindo[idKey]}</strong>?
              Esta ação não pode ser desfeita.
            </>
          }
          confirmar="Excluir"
          perigo
          busy={busy}
          onConfirm={confirmarExclusao}
          onClose={() => setExcluindo(null)}
        />
      )}
    </>
  );
}
