"""Sincroniza METADADOS do Firebird legado (DIGITALIZADOR.GDB, ao vivo) -> PostgreSQL.

Uso (no Bonfim, com PDV_FB_* no .env — mesmas credenciais/host do PDV):
    docker compose -f docker-compose.prod.yml exec backend \
        python -m scripts.sync_legado --dry-run     # só mostra o que faria
    docker compose -f docker-compose.prod.yml exec backend \
        python -m scripts.sync_legado               # aplica

O caminho do .gdb vem de --gdb ou da env LEGADO_FB_DATABASE
(padrão: C:/solution/data/DIGITALIZADOR.GDB, mesmo servidor do PDV).

Estratégia (espelha as regras do ETL — ver etl/migrate.py):
  - INCREMENTAL por PK: insere apenas linhas novas (id > max local); nunca apaga.
  - Catálogos (grupo, tipo_documento, índices, motivo, volume_storage): insere os
    que faltam; NÃO sobrescreve descrições (podem ter sido editadas no app novo).
  - USUARIO novo entra como no ETL: sem senha, e-mail não verificado, status
    pendente/bloqueado/desligado; login/e-mail deduplicados.
  - FKs órfãs viram NULL (contadas); documento sem registro pai é pulado.
  - --atualizar-registros: além de inserir, ATUALIZA as colunas dos registros já
    existentes (datas de conferência etc. mudam no legado).
  - Ao final, reajusta as sequences (evita colisão de id em inserts futuros do app).
  - Firebird em SOMENTE LEITURA; escrita no PostgreSQL em UMA transação.

Pré-requisito: base já populada (ETL/restore). Se estiver vazia, use o ETL.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from typing import Any

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine

GDB_PADRAO = os.environ.get("LEGADO_FB_DATABASE", "C:/solution/data/DIGITALIZADOR.GDB")
LOTE_INSERT = 1000  # linhas por executemany


# ----------------------------------------------------------------- conversões
def _txt(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).rstrip()
    return s or None


def _txt_req(v: Any, fallback: str) -> str:
    return _txt(v) or fallback


def _sn(v: Any, default: bool | None = None) -> bool | None:
    if v is None:
        return default
    s = str(v).strip().upper()
    if s == "S":
        return True
    if s == "N":
        return False
    return default


def _int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None


def _float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _dt(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    try:
        return datetime.fromisoformat(str(v).strip())
    except ValueError:
        return None


def _d(v: Any) -> date | None:
    dt = _dt(v)
    return dt.date() if dt else None


# ------------------------------------------------------------------- Firebird
def fb_conectar(gdb: str):  # type: ignore[no-untyped-def]
    import firebirdsql

    s = get_settings()
    if not (s.pdv_fb_host and s.pdv_fb_user and s.pdv_fb_password):
        print("ERRO: PDV_FB_HOST/USER/PASSWORD não configurados no .env", file=sys.stderr)
        raise SystemExit(2)
    return firebirdsql.connect(
        host=s.pdv_fb_host, port=s.pdv_fb_port, database=gdb,
        user=s.pdv_fb_user, password=s.pdv_fb_password, charset=s.pdv_fb_charset,
    )


def fb_linhas(fb, sql: str, params: tuple = ()) -> list[dict[str, Any]]:  # type: ignore[no-untyped-def]
    cur = fb.cursor()
    cur.execute(sql, params)
    cols = [d[0].strip().upper() for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


# ----------------------------------------------------------------- PostgreSQL
def pg_ids(conn, tabela: str, coluna: str = "id") -> set[int]:  # type: ignore[no-untyped-def]
    return {r[0] for r in conn.execute(text(f"SELECT {coluna} FROM {tabela}"))}


def inserir(conn, tabela: str, colunas: list[str], linhas: list[tuple],  # type: ignore[no-untyped-def]
            conflito: str = "DO NOTHING") -> int:
    if not linhas:
        return 0
    cols = ", ".join(colunas)
    binds = ", ".join(f":{c}" for c in colunas)
    sql = text(f"INSERT INTO {tabela} ({cols}) VALUES ({binds}) ON CONFLICT {conflito}")
    for i in range(0, len(linhas), LOTE_INSERT):
        fatia = linhas[i:i + LOTE_INSERT]
        conn.execute(sql, [dict(zip(colunas, ln)) for ln in fatia])
    return len(linhas)


# ------------------------------------------------------------------------ sync
def main() -> int:  # noqa: C901 - orquestração linear, espelha o ETL
    ap = argparse.ArgumentParser(description="Sync incremental Firebird legado -> PostgreSQL")
    ap.add_argument("--gdb", default=GDB_PADRAO, help=f"caminho do .gdb no servidor (padrão: {GDB_PADRAO})")
    ap.add_argument("--dry-run", action="store_true", help="não grava nada; só relata")
    ap.add_argument("--atualizar-registros", action="store_true",
                    help="além de inserir, atualiza registros existentes (datas de conferência etc.)")
    args = ap.parse_args()

    rel: dict[str, int] = {}
    fknull: dict[str, int] = {}

    print(f"Firebird: {get_settings().pdv_fb_host}:{args.gdb}")
    fb = fb_conectar(args.gdb)
    conn = engine.connect()
    trans = conn.begin()
    try:
        # -------- estado local (ids válidos) --------
        grupos = pg_ids(conn, "grupo")
        tipos = pg_ids(conn, "tipo_documento")
        usuarios = pg_ids(conn, "usuario")
        registros = pg_ids(conn, "registro")
        documentos = pg_ids(conn, "documento")
        motivos = pg_ids(conn, "motivo")
        ind_orig = pg_ids(conn, "indice_original")
        ind_apos = pg_ids(conn, "indice_apos_1999")
        volumes = pg_ids(conn, "volume_storage")
        if not registros or not documentos:
            print("ERRO: base local vazia — use o ETL para a carga inicial.", file=sys.stderr)
            return 2

        def uf(v: Any, tab: str) -> int | None:
            """FK de usuário: NULL se órfã (contada)."""
            iv = _int(v)
            if iv is None:
                return None
            if iv in usuarios:
                return iv
            fknull[tab] = fknull.get(tab, 0) + 1
            return None

        # -------- catálogos (insere só os que faltam) --------
        novas = [(g, _txt_req(r.get("DESCR"), f"Grupo {g}"), True)
                 for r in fb_linhas(fb, "select * from GRUPO_USUARIO")
                 if (g := _int(r["GRUPO_USUARIO"])) is not None and g not in grupos]
        rel["grupo"] = inserir(conn, "grupo", ["id", "descricao", "ativo"], novas)
        grupos |= {ln[0] for ln in novas}

        novas = []
        for r in fb_linhas(fb, "select * from TIPO_DOC"):
            t = _int(r["TIPO_DOC"])
            if t is None or t in tipos:
                continue
            situacao = (_txt(r.get("SITUACAO")) or "A").upper()
            novas.append((t, _txt_req(r.get("DESCR"), f"Tipo {t}"), _txt(r.get("DESCR_DETALHADO")),
                          _sn(r.get("FRENTE_VERSO"), False), _txt(r.get("INDICACAO_FRENTE")),
                          _int(r.get("QTDE_FOLHAS")) or 1, _int(r.get("PAGINA_INICIAL")),
                          situacao not in ("I", "N", "0")))
        rel["tipo_documento"] = inserir(
            conn, "tipo_documento",
            ["id", "descricao", "descricao_detalhada", "frente_verso", "indicacao_frente",
             "qtde_folhas", "pagina_inicial", "ativo"], novas)
        tipos |= {ln[0] for ln in novas}

        paginas = pg_ids(conn, "tipo_documento_pagina")
        novas = [(p, t, _sn(r.get("FRENTE")), _sn(r.get("VERSO")), _int(r.get("PAGINA")))
                 for r in fb_linhas(fb, "select * from TIPO_DOC_NITI")
                 if (p := _int(r["TIPO_DOC_NITI"])) is not None and p not in paginas
                 and (t := _int(r.get("TIPO_DOC"))) in tipos]
        rel["tipo_documento_pagina"] = inserir(
            conn, "tipo_documento_pagina", ["id", "tipo_doc_id", "frente", "verso", "pagina"], novas)

        pares = {(r[0], r[1]) for r in conn.execute(
            text("SELECT grupo_id, tipo_doc_id FROM grupo_tipo_documento"))}
        novas = []
        for r in fb_linhas(fb, "select * from GRUPO_TIPODOC"):
            g, t = _int(r.get("GRUPO_USUARIO")), _int(r.get("TIPO_DOC"))
            if g in grupos and t in tipos and (g, t) not in pares:
                pares.add((g, t))
                novas.append((g, t))
        rel["grupo_tipo_documento"] = inserir(
            conn, "grupo_tipo_documento", ["grupo_id", "tipo_doc_id"], novas)

        for origem, destino, conj in (("INDICE_ORIGINAL", "indice_original", ind_orig),
                                      ("INDICE_APOS_1999", "indice_apos_1999", ind_apos)):
            novas = [(i, _txt_req(r.get("DESCR"), f"{origem} {i}"))
                     for r in fb_linhas(fb, f"select * from {origem}")
                     if (i := _int(r[origem])) is not None and i not in conj]
            rel[destino] = inserir(conn, destino, ["id", "descricao"], novas)
            conj |= {ln[0] for ln in novas}

        novas = [(m, _txt_req(r.get("DESCR"), f"Motivo {m}"))
                 for r in fb_linhas(fb, "select * from MOTIVO")
                 if (m := _int(r["MOTIVO"])) is not None and m not in motivos]
        rel["motivo"] = inserir(conn, "motivo", ["id", "descricao"], novas)
        motivos |= {ln[0] for ln in novas}

        novas = []
        for r in fb_linhas(fb, "select * from HD"):
            h = _int(r["HD"])
            if h is None or h in volumes:
                continue
            novas.append((h, _txt_req(r.get("NOME_HD"), f"HD {h}"), _txt(r.get("PASTA_GRAVACAO")),
                          _txt(r.get("PASTA_THUMBNAIL")), _txt(r.get("PASTA_BACKUP")),
                          _txt(r.get("PASTA_ALTA")), _txt(r.get("SERIAL_FISICO")),
                          (_txt(r.get("STATUS")) or "A").upper() == "A",
                          _d(r.get("DATA_ATIVO")), _d(r.get("DATA_INATIVO"))))
        rel["volume_storage"] = inserir(
            conn, "volume_storage",
            ["id", "nome", "raiz_full", "raiz_thumb", "raiz_backup", "raiz_alta",
             "serial_fisico", "ativo", "data_ativo", "data_inativo"], novas)
        volumes |= {ln[0] for ln in novas}

        # -------- usuários novos (regras do ETL: sem senha, pendente) --------
        logins = {r[0].lower() for r in conn.execute(text("SELECT login FROM usuario"))}
        emails = {r[0].lower() for r in conn.execute(text("SELECT email FROM usuario"))}
        novas = []
        for r in fb_linhas(fb, "select * from USUARIO"):
            u = _int(r["USUARIO"])
            if u is None or u in usuarios:
                continue
            login = _txt_req(r.get("LOGIN"), f"user{u}")
            if login.lower() in logins:
                login = f"{login}_{u}"
            logins.add(login.lower())
            email = _txt(r.get("EMAIL"))
            if not email or "@" not in email or email.lower() in emails:
                email = f"user{u}@migrado.invalid"
            emails.add(email.lower())
            grupo = _int(r.get("GRUPO_USUARIO"))
            grupo = grupo if grupo in grupos else (min(grupos) if grupos else None)
            if _sn(r.get("ACESSO_CANCELADO"), False):
                st = "bloqueado"
            elif _dt(r.get("DESLIGAMENTO")):
                st = "desligado"
            else:
                st = "pendente"
            usuarios.add(u)
            novas.append((u, login, _txt(r.get("NOME")), email, None, False, st,
                          _sn(r.get("ADMINISTRADOR"), False), grupo, _int(r.get("TENTATIVA")) or 0,
                          _sn(r.get("ACESSO_CANCELADO"), False), _txt(r.get("ENDERECO")),
                          _txt(r.get("CIDADE")), _txt(r.get("FONE1")), _txt(r.get("FONE0")),
                          _d(r.get("CADASTRO")), _d(r.get("DESLIGAMENTO")), _txt(r.get("MOTIVO")),
                          _float(r.get("VLR_JPG_PASTA")), _float(r.get("VLR_JPG_UNIT")),
                          _float(r.get("VLR_DG_PASTA"))))
        rel["usuario"] = inserir(
            conn, "usuario",
            ["id", "login", "nome", "email", "senha_hash", "email_verificado", "status",
             "is_admin", "grupo_id", "tentativas_login", "acesso_cancelado", "endereco",
             "cidade", "fone_principal", "fone_secundario", "data_cadastro",
             "data_desligamento", "motivo_desligamento", "vlr_jpg_pasta", "vlr_jpg_unit",
             "vlr_dg_pasta"], novas)

        # -------- registro (novos; opcionalmente atualiza existentes) --------
        max_reg = max(registros)
        cols_registro = [
            "id", "titular", "contrato", "sepultado", "indice_original_id",
            "indice_apos_1999_id", "emissao_contrato_original", "ultimo_ano_pago", "lote",
            "locacao_arquivo", "situacao_emissao", "registro_bonfim", "usu_processo_jpg_id",
            "usu_data_jpg_ini", "usu_data_jpg_fim", "usu_ult_alteracao_id",
            "usu_processo_ajuste_id", "usu_data_ajuste_ini", "usu_data_ajuste_fim",
            "ajuste_dados_cliente", "data_dados_cliente", "data_conf_ult_ano",
            "usuario_conf_ult_ano_id", "data_conf_emissao", "usuario_conf_emissao_id",
            "data_conf_emissao_contrato", "usuario_conf_emissao_contrato_id", "cadastro"]

        def linha_registro(r: dict[str, Any]) -> tuple:
            rid = _int(r["REGISTRO"])
            io, ia = _int(r.get("INDICE_ORIGINAL")), _int(r.get("INDICE_APOS_1999"))
            return (rid, _int(r.get("TITULAR")), _int(r.get("CONTRATO")), _int(r.get("SEPULTADO")),
                    io if io in ind_orig else None, ia if ia in ind_apos else None,
                    _d(r.get("EMISSAO_CONTRATO_ORIGINAL")), _int(r.get("ULTIMO_ANO_PAGO")),
                    _txt(r.get("LOTE")), _txt(r.get("LOCACAO_ARQUIVO")),
                    _txt(r.get("SITUACAO_EMISSAO")), _int(r.get("REGISTRO_BONFIM")),
                    uf(r.get("USU_PROCESSO_JPG"), "registro"), _d(r.get("USU_DATA_JPG_INI")),
                    _d(r.get("USU_DATA_JPG_FIM")), uf(r.get("USU_ULT_ALTERACAO"), "registro"),
                    uf(r.get("USU_PROCESSO_AJUSTE"), "registro"), _d(r.get("USU_DATA_AJUSTE_INI")),
                    _d(r.get("USU_DATA_AJUSTE_FIM")), _int(r.get("AJUSTE_DADOS_CLIENTE")),
                    _d(r.get("DATA_DADOS_CLIENTE")), _d(r.get("DATA_CONF_ULT_ANO")),
                    uf(r.get("USUARIO_CONF_ULT_ANO"), "registro"), _d(r.get("DATA_CONF_EMISSAO")),
                    uf(r.get("USUARIO_CONF_EMISSAO"), "registro"),
                    _d(r.get("DATA_CONF_EMISSAO_CONTRATO")),
                    uf(r.get("USUARIO_CONF_EMISSAO_CONTRATO"), "registro"), _dt(r.get("CADASTRO")))

        novos_reg = []
        for r in fb_linhas(fb, "select * from REGISTRO where REGISTRO > ?", (max_reg,)):
            ln = linha_registro(r)
            if ln[0] is None:
                continue
            registros.add(ln[0])
            novos_reg.append(ln)
        rel["registro"] = inserir(conn, "registro", cols_registro, novos_reg)

        if args.atualizar_registros:
            upd = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols_registro if c != "id")
            todos = [linha_registro(r) for r in
                     fb_linhas(fb, "select * from REGISTRO where REGISTRO <= ?", (max_reg,))]
            todos = [ln for ln in todos if ln[0] is not None]
            rel["registro_atualizado"] = inserir(
                conn, "registro", cols_registro, todos, conflito=f"(id) DO UPDATE SET {upd}")

        # -------- documento + documento_legado (novos) --------
        max_doc = max(documentos)
        imgs = fb_linhas(fb, "select * from REGISTRO_IMAGE where REGISTRO_IMAGE > ?", (max_doc,))
        novas_doc, novas_leg, pulados = [], [], 0
        for r in imgs:
            did, reg = _int(r["REGISTRO_IMAGE"]), _int(r.get("REGISTRO"))
            if did is None or reg not in registros:
                pulados += 1
                continue
            documentos.add(did)
            tipo = _int(r.get("TIPO_DOC"))
            face = _txt(r.get("FRENTE"))
            novas_doc.append((did, reg, tipo if tipo in tipos else None,
                              face if face in ("F", "V") else None,
                              _int(r.get("NR_FOLHA")), _int(r.get("TOTAL_FOLHAS")),
                              _int(r.get("GUIA")), _txt(r.get("NR_GUIA")), _txt(r.get("PASTA")),
                              _sn(r.get("REFUGADA"), False), _sn(r.get("USO"), True),
                              _dt(r.get("AUDITADA_EM")), uf(r.get("AUDITADA_POR"), "documento"),
                              _sn(r.get("ACEITOU_QTDE_SEPULTADO")), _d(r.get("DATA_CONF_SEPULTADO")),
                              uf(r.get("USUARIO_CONF_SEP"), "documento"), _int(r.get("ID_SEPULTADO")),
                              uf(r.get("USUARIO_INSERT"), "documento"),
                              uf(r.get("USUARIO_ULT_ALTERACAO"), "documento"), _dt(r.get("CADASTRO"))))
            novas_leg.append((did, did, _txt(r.get("IMAGE")), _txt(r.get("IMAGE_THUMBNAIL")),
                              _txt(r.get("IMAGE_BACKUP")), _int(r.get("ID_HD_IMAGE")),
                              _int(r.get("ID_HD_THUMBNAIL")), _int(r.get("ID_HD_BACKUP")),
                              _txt(r.get("NOME_ARQUIVO")), _txt(r.get("NOME_ARQ_TEMP")),
                              _txt(r.get("MAQUINA_ORIGEM")), _txt(r.get("VOLUME_ORIGEM")),
                              _txt(r.get("CAMINHO_ORIGEM")), _float(r.get("TAM_ARQ_LOGICO")), None))
        rel["documento"] = inserir(
            conn, "documento",
            ["id", "registro_id", "tipo_doc_id", "face", "nr_folha", "total_folhas", "guia",
             "nr_guia", "pasta", "refugada", "em_uso", "auditada_em", "auditada_por_id",
             "aceitou_qtde_sepultado", "data_conf_sepultado", "usuario_conf_sep_id",
             "id_sepultado", "usuario_insert_id", "usuario_ult_alteracao_id", "cadastro"],
            novas_doc)
        rel["documento_legado"] = inserir(
            conn, "documento_legado",
            ["documento_id", "registro_image_id", "legacy_image_path", "legacy_thumb_path",
             "legacy_backup_path", "legacy_hd_image", "legacy_hd_thumb", "legacy_hd_backup",
             "nome_arquivo", "nome_arq_temp", "maquina_origem", "volume_origem",
             "caminho_origem", "tam_arq_logico", "migrado_em"],
            novas_leg, conflito="(documento_id) DO NOTHING")
        if pulados:
            rel["documento_pulado(sem_pai)"] = pulados

        # -------- refugo (novos) --------
        max_ref = max(pg_ids(conn, "refugo"), default=0)
        novas = []
        for r in fb_linhas(fb, "select * from REGISTRO_REFUGO where REGISTRO_REFUGO > ?", (max_ref,)):
            fid = _int(r["REGISTRO_REFUGO"])
            if fid is None:
                continue
            reg, doc, mot = _int(r.get("REGISTRO")), _int(r.get("REGISTRO_IMAGE")), _int(r.get("MOTIVO"))
            usu, usr = _int(r.get("USUARIO")), _int(r.get("USUARIO_RESOLVIDO"))
            novas.append((fid, reg if reg in registros else None, doc if doc in documentos else None,
                          mot if mot in motivos else None, _dt(r.get("DATA")),
                          usu if usu in usuarios else None, _txt(r.get("COMENTARIO")),
                          _sn(r.get("RESOLVIDO"), False), _dt(r.get("DATA_RESOLVIDO")),
                          usr if usr in usuarios else None, _txt(r.get("COMENTARIO_RESOLVIDO"))))
        rel["refugo"] = inserir(
            conn, "refugo",
            ["id", "registro_id", "documento_id", "motivo_id", "data", "usuario_id",
             "comentario", "resolvido", "data_resolvido", "usuario_resolvido_id",
             "comentario_resolvido"], novas)

        # -------- sequences --------
        for t in ("grupo", "tipo_documento", "tipo_documento_pagina", "indice_original",
                  "indice_apos_1999", "motivo", "volume_storage", "usuario",
                  "registro", "documento", "refugo"):
            conn.execute(text(
                "SELECT setval(pg_get_serial_sequence(:t, 'id'), "
                "(SELECT COALESCE(max(id), 1) FROM " + t + "))"), {"t": t})

        # -------- fecha --------
        print("\n== Sincronização" + (" (DRY-RUN — nada gravado)" if args.dry_run else "") + " ==")
        for k, v in rel.items():
            print(f"  {k:28} {v:>8}")
        if fknull:
            print("  FKs de usuário nulificadas:", dict(fknull))
        if args.dry_run:
            trans.rollback()
        else:
            trans.commit()
            print("\nCommit OK.")
        return 0
    except Exception:
        trans.rollback()
        raise
    finally:
        conn.close()
        fb.close()


if __name__ == "__main__":
    raise SystemExit(main())
