import { useEffect, useState } from "react";

import { api, ApiError, jsonBody } from "../api/client";
import type { Usuario } from "../api/types";
import { Modal } from "../components/Modal";

interface Grupo {
  id: number;
  descricao: string;
  ativo: boolean;
}

type Form = { login: string; nome: string; email: string; grupo_id: number | string; is_admin: boolean };

export function UsuariosPage() {
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [grupos, setGrupos] = useState<Grupo[]>([]);
  const [fv, setFv] = useState<Record<string, string>>({});
  const [form, setForm] = useState<Form | null>(null);
  const [editId, setEditId] = useState<number | null>(null);
  const [msg, setMsg] = useState<{ t: "ok" | "err"; s: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function carregar() {
    setUsuarios(await api<Usuario[]>("/usuarios"));
  }
  useEffect(() => {
    (async () => {
      try {
        setGrupos(await api<Grupo[]>("/grupos"));
        await carregar();
      } catch (e) {
        setMsg({ t: "err", s: e instanceof ApiError ? e.detail : "Falha ao carregar" });
      }
    })();
  }, []);

  const grupoNome = (id: number) => grupos.find((g) => g.id === id)?.descricao ?? `#${id}`;

  function novo() {
    setForm({ login: "", nome: "", email: "", grupo_id: grupos[0]?.id ?? "", is_admin: false });
    setEditId(null);
    setMsg(null);
  }
  function editar(u: Usuario) {
    setForm({ login: u.login, nome: u.nome ?? "", email: u.email, grupo_id: u.grupo_id, is_admin: u.is_admin });
    setEditId(u.id);
    setMsg(null);
  }

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setBusy(true);
    setMsg(null);
    try {
      if (editId == null) {
        await api(
          "/usuarios",
          jsonBody({
            login: form.login,
            nome: form.nome || null,
            email: form.email,
            grupo_id: Number(form.grupo_id),
            is_admin: form.is_admin,
          }),
        );
        setMsg({ t: "ok", s: "Usuário criado (pendente de confirmação de e-mail)." });
      } else {
        await api(`/usuarios/${editId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            nome: form.nome || null,
            grupo_id: Number(form.grupo_id),
            is_admin: form.is_admin,
          }),
        });
        setMsg({ t: "ok", s: "Usuário atualizado." });
      }
      setForm(null);
      setEditId(null);
      await carregar();
    } catch (err) {
      setMsg({ t: "err", s: err instanceof ApiError ? err.detail : "Falha ao salvar" });
    } finally {
      setBusy(false);
    }
  }

  async function acao(u: Usuario, tipo: "bloquear" | "desbloquear") {
    setMsg(null);
    try {
      await api(`/usuarios/${u.id}/${tipo}`, { method: "POST" });
      await carregar();
    } catch (err) {
      setMsg({ t: "err", s: err instanceof ApiError ? err.detail : "Falha" });
    }
  }

  const statusPill = (s: string) => {
    const cls = s === "ativo" ? "accent" : s === "pendente" ? "amber" : "crit";
    return <span className={`pill ${cls}`}>{s}</span>;
  };

  const filtrados = usuarios.filter((u) => {
    if (fv.nome && !`${u.login} ${u.nome ?? ""}`.toLowerCase().includes(fv.nome.toLowerCase()))
      return false;
    if (fv.status && u.status !== fv.status) return false;
    if (fv.grupo && u.grupo_id !== Number(fv.grupo)) return false;
    const d = u.data_cadastro ? String(u.data_cadastro).slice(0, 10) : "";
    if (fv.cad_de && (!d || d < fv.cad_de)) return false;
    if (fv.cad_ate && (!d || d > fv.cad_ate)) return false;
    return true;
  });

  return (
    <>
      <div className="page-head">
        <p className="eyebrow">Tabelas</p>
        <h1>Usuários</h1>
        <p className="muted">Cadastro de usuários e controle de acesso.</p>
      </div>

      {msg && <div className={`alert ${msg.t === "ok" ? "ok" : "err"}`}>{msg.s}</div>}

      <div className="card filtros">
        <div className="field">
          <label>Nome</label>
          <input value={fv.nome ?? ""} placeholder="Buscar…" onChange={(e) => setFv({ ...fv, nome: e.target.value })} />
        </div>
        <div className="field">
          <label>Situação</label>
          <select value={fv.status ?? ""} onChange={(e) => setFv({ ...fv, status: e.target.value })}>
            <option value="">Todas</option>
            <option value="ativo">Ativo</option>
            <option value="pendente">Pendente</option>
            <option value="bloqueado">Bloqueado</option>
            <option value="desligado">Desligado</option>
          </select>
        </div>
        <div className="field">
          <label>Setor</label>
          <select value={fv.grupo ?? ""} onChange={(e) => setFv({ ...fv, grupo: e.target.value })}>
            <option value="">Todos</option>
            {grupos.map((g) => (
              <option key={g.id} value={g.id}>
                {g.descricao}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Cadastro de</label>
          <input type="date" value={fv.cad_de ?? ""} onChange={(e) => setFv({ ...fv, cad_de: e.target.value })} />
        </div>
        <div className="field">
          <label>Cadastro até</label>
          <input type="date" value={fv.cad_ate ?? ""} onChange={(e) => setFv({ ...fv, cad_ate: e.target.value })} />
        </div>
        <button className="btn ghost sm" type="button" onClick={() => setFv({})}>
          Limpar
        </button>
      </div>

      <div className="toolbar">
        <button className="btn" onClick={novo}>
          + Novo usuário
        </button>
        <span className="spacer" />
        <span className="muted">
          {filtrados.length}
          {filtrados.length !== usuarios.length ? ` de ${usuarios.length}` : ""} usuário(s)
        </span>
      </div>

      {form && (
        <Modal
          titulo={editId == null ? "Novo usuário" : `Editar usuário #${editId}`}
          onClose={() => setForm(null)}
          largura="40rem"
        >
          <form onSubmit={salvar}>
            <div className="form-grid">
              {editId == null && (
                <>
                  <div className="field">
                    <label>Login</label>
                    <input value={form.login} required autoFocus onChange={(e) => setForm({ ...form, login: e.target.value })} />
                  </div>
                  <div className="field">
                    <label>E-mail</label>
                    <input type="email" value={form.email} required onChange={(e) => setForm({ ...form, email: e.target.value })} />
                  </div>
                </>
              )}
              <div className="field full">
                <label>Nome</label>
                <input value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} />
              </div>
              <div className="field">
                <label>Setor</label>
                <select value={form.grupo_id} onChange={(e) => setForm({ ...form, grupo_id: e.target.value })}>
                  {grupos.map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.descricao}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Administrador</label>
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={form.is_admin}
                    onChange={(e) => setForm({ ...form, is_admin: e.target.checked })}
                  />
                  Sim
                </label>
              </div>
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

      <div className="card" style={{ padding: 0, marginTop: form ? "1.2rem" : undefined }}>
        <div className="tablewrap" style={{ border: "none" }}>
          <table>
            <thead>
              <tr>
                <th>Login</th>
                <th>Nome</th>
                <th>E-mail</th>
                <th>Setor</th>
                <th>Admin</th>
                <th>Situação</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filtrados.map((u) => (
                <tr key={u.id}>
                  <td>{u.login}</td>
                  <td>{u.nome ?? "—"}</td>
                  <td className="muted">{u.email}</td>
                  <td>{grupoNome(u.grupo_id)}</td>
                  <td>{u.is_admin ? "Sim" : "—"}</td>
                  <td>{statusPill(u.status)}</td>
                  <td style={{ whiteSpace: "nowrap", textAlign: "right" }}>
                    <button className="btn soft sm" onClick={() => editar(u)}>
                      Editar
                    </button>{" "}
                    {u.status === "bloqueado" ? (
                      <button className="btn soft sm" onClick={() => acao(u, "desbloquear")}>
                        Desbloquear
                      </button>
                    ) : (
                      <button className="btn danger sm" onClick={() => acao(u, "bloquear")}>
                        Bloquear
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
