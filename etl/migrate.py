"""Migrador Firebird -> PostgreSQL.

Estratégia:
  1) parse_dump(): varre o dump uma vez e separa cada tabela em _work/<TABELA>.jsonl
     (descarta SEQ_IMAGEM/TEMP; pode limitar REGISTRO_IMAGE via max_images).
  2) load_all(): carrega em ordem de dependência (FK). IDs legados são preservados.
     FKs órfãs viram NULL (contabilizadas); linhas sem pai obrigatório são puladas.
  3) reset_sequences(): ajusta as sequences IDENTITY para max(id).

Relatório de conciliação em self.report.
"""
from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import psycopg

from etl import casts as c
from etl.fb_parser import iter_inserts

DESCARTAR = {"SEQ_IMAGEM", "TEMP"}


def _d(v: Any) -> date | None:
    dt = c.to_dt(v)
    return dt.date() if dt else None


class Migrator:
    def __init__(self, conn: psycopg.Connection, work_dir: Path, max_images: int = 0) -> None:
        self.conn = conn
        self.work = Path(work_dir)
        self.work.mkdir(parents=True, exist_ok=True)
        self.max_images = max_images
        # conjuntos de IDs válidos (preenchidos ao carregar os pais)
        self.grupos: set[int] = set()
        self.tipos: set[int] = set()
        self.usuarios: set[int] = set()
        self.registros: set[int] = set()
        self.motivos: set[int] = set()
        self.indices_orig: set[int] = set()
        self.indices_apos: set[int] = set()
        self.volumes: set[int] = set()
        self.documentos: set[int] = set()
        self.report: dict[str, dict[str, int]] = {
            "origem": {},
            "carregado": defaultdict(int),
            "pulado": defaultdict(int),
            "fk_nulificada": defaultdict(int),
        }

    # ----------------------------------------------------------------- parse
    def parse_dump(self, dump: str | Path) -> None:
        arquivos: dict[str, Any] = {}
        contagem: dict[str, int] = defaultdict(int)
        imagens = 0
        try:
            for tabela, linha in iter_inserts(dump):
                if tabela in DESCARTAR:
                    continue
                if tabela == "REGISTRO_IMAGE" and self.max_images and imagens >= self.max_images:
                    continue
                if tabela == "REGISTRO_IMAGE":
                    imagens += 1
                fh = arquivos.get(tabela)
                if fh is None:
                    fh = open(self.work / f"{tabela}.jsonl", "w", encoding="utf-8")
                    arquivos[tabela] = fh
                fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
                contagem[tabela] += 1
        finally:
            for fh in arquivos.values():
                fh.close()
        self.report["origem"] = dict(contagem)

    def _read(self, tabela: str) -> Iterator[dict[str, Any]]:
        caminho = self.work / f"{tabela}.jsonl"
        if not caminho.exists():
            return
        with open(caminho, encoding="utf-8") as fh:
            for linha in fh:
                yield json.loads(linha)

    # ------------------------------------------------------------------ copy
    def _copy(self, tabela: str, colunas: list[str], linhas: Iterator[tuple[Any, ...]]) -> int:
        n = 0
        cols = ", ".join(colunas)
        with self.conn.cursor() as cur, cur.copy(f"COPY {tabela} ({cols}) FROM STDIN") as cp:
            for linha in linhas:
                cp.write_row(linha)
                n += 1
        self.conn.commit()
        self.report["carregado"][tabela] = n
        return n

    def _fk(self, valor: Any, validos: set[int]) -> int | None:
        """Mantém o FK se o pai existe; senão NULL (e conta)."""
        iv = c.to_int(valor)
        if iv is None:
            return None
        if iv in validos:
            return iv
        return -1  # sinaliza órfão (o chamador conta e troca por None)

    # --------------------------------------------------------------- catálogos
    def load_grupo(self) -> None:
        def linhas() -> Iterator[tuple[Any, ...]]:
            for r in self._read("GRUPO_USUARIO"):
                gid = c.to_int(r["GRUPO_USUARIO"])
                if gid is None:
                    continue
                self.grupos.add(gid)
                yield (gid, c.txt_req(r.get("DESCR"), f"Grupo {gid}"), True)

        self._copy("grupo", ["id", "descricao", "ativo"], linhas())

    def load_tipo_documento(self) -> None:
        def linhas() -> Iterator[tuple[Any, ...]]:
            for r in self._read("TIPO_DOC"):
                tid = c.to_int(r["TIPO_DOC"])
                if tid is None:
                    continue
                self.tipos.add(tid)
                situacao = (c.txt(r.get("SITUACAO")) or "A").upper()
                yield (
                    tid,
                    c.txt_req(r.get("DESCR"), f"Tipo {tid}"),
                    c.txt(r.get("DESCR_DETALHADO")),
                    c.sn_bool(r.get("FRENTE_VERSO"), False),
                    c.txt(r.get("INDICACAO_FRENTE")),
                    c.to_int(r.get("QTDE_FOLHAS")) or 1,
                    c.to_int(r.get("PAGINA_INICIAL")),
                    situacao not in ("I", "N", "0"),
                )

        self._copy(
            "tipo_documento",
            ["id", "descricao", "descricao_detalhada", "frente_verso",
             "indicacao_frente", "qtde_folhas", "pagina_inicial", "ativo"],
            linhas(),
        )

    def load_tipo_documento_pagina(self) -> None:
        def linhas() -> Iterator[tuple[Any, ...]]:
            for r in self._read("TIPO_DOC_NITI"):
                pid = c.to_int(r["TIPO_DOC_NITI"])
                tid = c.to_int(r.get("TIPO_DOC"))
                if pid is None or tid not in self.tipos:
                    self.report["pulado"]["tipo_documento_pagina"] += 1
                    continue
                yield (pid, tid, c.sn_bool(r.get("FRENTE")), c.sn_bool(r.get("VERSO")),
                       c.to_int(r.get("PAGINA")))

        self._copy(
            "tipo_documento_pagina",
            ["id", "tipo_doc_id", "frente", "verso", "pagina"],
            linhas(),
        )

    def load_grupo_tipo_documento(self) -> None:
        vistos: set[tuple[int, int]] = set()

        def linhas() -> Iterator[tuple[Any, ...]]:
            for r in self._read("GRUPO_TIPODOC"):
                g = c.to_int(r.get("GRUPO_USUARIO"))
                t = c.to_int(r.get("TIPO_DOC"))
                if g not in self.grupos or t not in self.tipos or (g, t) in vistos:
                    self.report["pulado"]["grupo_tipo_documento"] += 1
                    continue
                vistos.add((g, t))
                yield (g, t)

        self._copy("grupo_tipo_documento", ["grupo_id", "tipo_doc_id"], linhas())

    def _load_indice(self, origem: str, destino: str, conj: set[int]) -> None:
        def linhas() -> Iterator[tuple[Any, ...]]:
            for r in self._read(origem):
                iid = c.to_int(r[origem])
                if iid is None:
                    continue
                conj.add(iid)
                yield (iid, c.txt_req(r.get("DESCR"), f"{origem} {iid}"))

        self._copy(destino, ["id", "descricao"], linhas())

    def load_motivo(self) -> None:
        def linhas() -> Iterator[tuple[Any, ...]]:
            for r in self._read("MOTIVO"):
                mid = c.to_int(r["MOTIVO"])
                if mid is None:
                    continue
                self.motivos.add(mid)
                yield (mid, c.txt_req(r.get("DESCR"), f"Motivo {mid}"))

        self._copy("motivo", ["id", "descricao"], linhas())

    def load_volume_storage(self) -> None:
        def linhas() -> Iterator[tuple[Any, ...]]:
            for r in self._read("HD"):
                hid = c.to_int(r["HD"])
                if hid is None:
                    continue
                self.volumes.add(hid)
                yield (
                    hid,
                    c.txt_req(r.get("NOME_HD"), f"HD {hid}"),
                    c.txt(r.get("PASTA_GRAVACAO")),
                    c.txt(r.get("PASTA_THUMBNAIL")),
                    c.txt(r.get("PASTA_BACKUP")),
                    c.txt(r.get("PASTA_ALTA")),
                    c.txt(r.get("SERIAL_FISICO")),
                    (c.txt(r.get("STATUS")) or "A").upper() == "A",
                    _d(r.get("DATA_ATIVO")),
                    _d(r.get("DATA_INATIVO")),
                )

        self._copy(
            "volume_storage",
            ["id", "nome", "raiz_full", "raiz_thumb", "raiz_backup", "raiz_alta",
             "serial_fisico", "ativo", "data_ativo", "data_inativo"],
            linhas(),
        )

    def load_parametro(self) -> None:
        r = next(self._read("PARAM"), None)
        if r is None:
            return

        def vol(x: Any) -> int | None:
            iv = c.to_int(x)
            return iv if iv in self.volumes else None

        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO parametro (id, volume_gravacao_id, volume_backup_id,
                    volume_thumbnail_id, locacao_atual, gravacao_datacenter, backup_datacenter)
                VALUES (true, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    volume_gravacao_id = EXCLUDED.volume_gravacao_id,
                    volume_backup_id = EXCLUDED.volume_backup_id,
                    volume_thumbnail_id = EXCLUDED.volume_thumbnail_id,
                    locacao_atual = EXCLUDED.locacao_atual,
                    gravacao_datacenter = EXCLUDED.gravacao_datacenter,
                    backup_datacenter = EXCLUDED.backup_datacenter
                """,
                (
                    vol(r.get("ID_HD_GRACAVAO")), vol(r.get("ID_HD_BACKUP")),
                    vol(r.get("ID_HD_THUMBNAIL")), c.txt(r.get("LOCACAO_ATUAL")),
                    c.sn_bool(r.get("GRAVACAO_DATACENTER"), False),
                    c.sn_bool(r.get("BACKUP_DATACENTER"), False),
                ),
            )
        self.conn.commit()
        self.report["carregado"]["parametro"] = 1

    # ------------------------------------------------------------------ usuário
    def load_usuario(self) -> None:
        default_grupo = min(self.grupos) if self.grupos else None
        emails: set[str] = set()
        logins: set[str] = set()

        def status(r: dict[str, Any]) -> str:
            if c.sn_bool(r.get("ACESSO_CANCELADO"), False):
                return "bloqueado"
            if c.to_dt(r.get("DESLIGAMENTO")):
                return "desligado"
            return "pendente"

        def linhas() -> Iterator[tuple[Any, ...]]:
            for r in self._read("USUARIO"):
                uid = c.to_int(r["USUARIO"])
                if uid is None:
                    continue
                login = c.txt_req(r.get("LOGIN"), f"user{uid}")
                if login.lower() in logins:
                    login = f"{login}_{uid}"
                logins.add(login.lower())
                email = c.txt(r.get("EMAIL"))
                if not email or "@" not in email or email.lower() in emails:
                    email = f"user{uid}@migrado.invalid"
                emails.add(email.lower())
                grupo = c.to_int(r.get("GRUPO_USUARIO"))
                grupo = grupo if grupo in self.grupos else default_grupo
                self.usuarios.add(uid)
                yield (
                    uid, login, c.txt(r.get("NOME")), email,
                    None,               # senha_hash (reset obrigatório)
                    False,              # email_verificado
                    status(r),
                    c.sn_bool(r.get("ADMINISTRADOR"), False),
                    grupo,
                    c.to_int(r.get("TENTATIVA")) or 0,
                    c.sn_bool(r.get("ACESSO_CANCELADO"), False),
                    c.txt(r.get("ENDERECO")), c.txt(r.get("CIDADE")),
                    c.txt(r.get("FONE1")), c.txt(r.get("FONE0")),  # FONE2 = senha legada -> descartado
                    _d(r.get("CADASTRO")), _d(r.get("DESLIGAMENTO")), c.txt(r.get("MOTIVO")),
                    c.to_float(r.get("VLR_JPG_PASTA")), c.to_float(r.get("VLR_JPG_UNIT")),
                    c.to_float(r.get("VLR_DG_PASTA")),
                )

        self._copy(
            "usuario",
            ["id", "login", "nome", "email", "senha_hash", "email_verificado", "status",
             "is_admin", "grupo_id", "tentativas_login", "acesso_cancelado", "endereco",
             "cidade", "fone_principal", "fone_secundario", "data_cadastro",
             "data_desligamento", "motivo_desligamento", "vlr_jpg_pasta", "vlr_jpg_unit",
             "vlr_dg_pasta"],
            linhas(),
        )

    def load_parametro_usuario(self) -> None:
        def linhas() -> Iterator[tuple[Any, ...]]:
            for r in self._read("PARAM_USUARIO"):
                pid = c.to_int(r["PARAM_USUARIO"])
                uid = c.to_int(r.get("USUARIO"))
                if pid is None or uid not in self.usuarios:
                    self.report["pulado"]["parametro_usuario"] += 1
                    continue
                yield (pid, uid, c.txt(r.get("ULT_LER_PASTA")), c.sn_bool(r.get("APAGA_ORIGEM"), False))

        self._copy(
            "parametro_usuario",
            ["id", "usuario_id", "ult_ler_pasta", "apaga_origem"],
            linhas(),
        )

    # ------------------------------------------------------------------ domínio
    def load_registro(self) -> None:
        def uf(v: Any) -> int | None:
            r = self._fk(v, self.usuarios)
            if r == -1:
                self.report["fk_nulificada"]["registro"] += 1
                return None
            return r

        def linhas() -> Iterator[tuple[Any, ...]]:
            for r in self._read("REGISTRO"):
                rid = c.to_int(r["REGISTRO"])
                if rid is None:
                    continue
                io = c.to_int(r.get("INDICE_ORIGINAL"))
                ia = c.to_int(r.get("INDICE_APOS_1999"))
                self.registros.add(rid)
                yield (
                    rid, c.to_int(r.get("TITULAR")), c.to_int(r.get("CONTRATO")),
                    c.to_int(r.get("SEPULTADO")),
                    io if io in self.indices_orig else None,
                    ia if ia in self.indices_apos else None,
                    _d(r.get("EMISSAO_CONTRATO_ORIGINAL")), c.to_int(r.get("ULTIMO_ANO_PAGO")),
                    c.txt(r.get("LOTE")), c.txt(r.get("LOCACAO_ARQUIVO")),
                    c.txt(r.get("SITUACAO_EMISSAO")), c.to_int(r.get("REGISTRO_BONFIM")),
                    uf(r.get("USU_PROCESSO_JPG")), _d(r.get("USU_DATA_JPG_INI")),
                    _d(r.get("USU_DATA_JPG_FIM")), uf(r.get("USU_ULT_ALTERACAO")),
                    uf(r.get("USU_PROCESSO_AJUSTE")), _d(r.get("USU_DATA_AJUSTE_INI")),
                    _d(r.get("USU_DATA_AJUSTE_FIM")), c.to_int(r.get("AJUSTE_DADOS_CLIENTE")),
                    _d(r.get("DATA_DADOS_CLIENTE")), _d(r.get("DATA_CONF_ULT_ANO")),
                    uf(r.get("USUARIO_CONF_ULT_ANO")), _d(r.get("DATA_CONF_EMISSAO")),
                    uf(r.get("USUARIO_CONF_EMISSAO")), _d(r.get("DATA_CONF_EMISSAO_CONTRATO")),
                    uf(r.get("USUARIO_CONF_EMISSAO_CONTRATO")), c.to_dt(r.get("CADASTRO")),
                )

        self._copy(
            "registro",
            ["id", "titular", "contrato", "sepultado", "indice_original_id",
             "indice_apos_1999_id", "emissao_contrato_original", "ultimo_ano_pago", "lote",
             "locacao_arquivo", "situacao_emissao", "registro_bonfim", "usu_processo_jpg_id",
             "usu_data_jpg_ini", "usu_data_jpg_fim", "usu_ult_alteracao_id",
             "usu_processo_ajuste_id", "usu_data_ajuste_ini", "usu_data_ajuste_fim",
             "ajuste_dados_cliente", "data_dados_cliente", "data_conf_ult_ano",
             "usuario_conf_ult_ano_id", "data_conf_emissao", "usuario_conf_emissao_id",
             "data_conf_emissao_contrato", "usuario_conf_emissao_contrato_id", "cadastro"],
            linhas(),
        )

    def load_documento(self) -> None:
        def uf(v: Any) -> int | None:
            r = self._fk(v, self.usuarios)
            if r == -1:
                self.report["fk_nulificada"]["documento"] += 1
                return None
            return r

        def linhas() -> Iterator[tuple[Any, ...]]:
            for r in self._read("REGISTRO_IMAGE"):
                did = c.to_int(r["REGISTRO_IMAGE"])
                reg = c.to_int(r.get("REGISTRO"))
                if did is None or reg not in self.registros:
                    self.report["pulado"]["documento"] += 1
                    continue
                self.documentos.add(did)
                tipo = c.to_int(r.get("TIPO_DOC"))
                face = c.txt(r.get("FRENTE"))
                yield (
                    did, reg, tipo if tipo in self.tipos else None,
                    face if face in ("F", "V") else None,
                    c.to_int(r.get("NR_FOLHA")), c.to_int(r.get("TOTAL_FOLHAS")),
                    c.to_int(r.get("GUIA")), c.txt(r.get("NR_GUIA")), c.txt(r.get("PASTA")),
                    c.sn_bool(r.get("REFUGADA"), False), c.sn_bool(r.get("USO"), True),
                    c.to_dt(r.get("AUDITADA_EM")), uf(r.get("AUDITADA_POR")),
                    c.sn_bool(r.get("ACEITOU_QTDE_SEPULTADO")), _d(r.get("DATA_CONF_SEPULTADO")),
                    uf(r.get("USUARIO_CONF_SEP")), c.to_int(r.get("ID_SEPULTADO")),
                    uf(r.get("USUARIO_INSERT")), uf(r.get("USUARIO_ULT_ALTERACAO")),
                    c.to_dt(r.get("CADASTRO")),
                )

        self._copy(
            "documento",
            ["id", "registro_id", "tipo_doc_id", "face", "nr_folha", "total_folhas", "guia",
             "nr_guia", "pasta", "refugada", "em_uso", "auditada_em", "auditada_por_id",
             "aceitou_qtde_sepultado", "data_conf_sepultado", "usuario_conf_sep_id",
             "id_sepultado", "usuario_insert_id", "usuario_ult_alteracao_id", "cadastro"],
            linhas(),
        )

    def load_documento_legado(self) -> None:
        def linhas() -> Iterator[tuple[Any, ...]]:
            for r in self._read("REGISTRO_IMAGE"):
                did = c.to_int(r["REGISTRO_IMAGE"])
                if did not in self.documentos:
                    continue
                yield (
                    did, did, c.txt(r.get("IMAGE")), c.txt(r.get("IMAGE_THUMBNAIL")),
                    c.txt(r.get("IMAGE_BACKUP")), c.to_int(r.get("ID_HD_IMAGE")),
                    c.to_int(r.get("ID_HD_THUMBNAIL")), c.to_int(r.get("ID_HD_BACKUP")),
                    c.txt(r.get("NOME_ARQUIVO")), c.txt(r.get("NOME_ARQ_TEMP")),
                    c.txt(r.get("MAQUINA_ORIGEM")), c.txt(r.get("VOLUME_ORIGEM")),
                    c.txt(r.get("CAMINHO_ORIGEM")), c.to_float(r.get("TAM_ARQ_LOGICO")), None,
                )

        self._copy(
            "documento_legado",
            ["documento_id", "registro_image_id", "legacy_image_path", "legacy_thumb_path",
             "legacy_backup_path", "legacy_hd_image", "legacy_hd_thumb", "legacy_hd_backup",
             "nome_arquivo", "nome_arq_temp", "maquina_origem", "volume_origem",
             "caminho_origem", "tam_arq_logico", "migrado_em"],
            linhas(),
        )

    def load_refugo(self) -> None:
        def linhas() -> Iterator[tuple[Any, ...]]:
            for r in self._read("REGISTRO_REFUGO"):
                fid = c.to_int(r["REGISTRO_REFUGO"])
                if fid is None:
                    continue
                reg = c.to_int(r.get("REGISTRO"))
                doc = c.to_int(r.get("REGISTRO_IMAGE"))
                mot = c.to_int(r.get("MOTIVO"))
                usu = c.to_int(r.get("USUARIO"))
                usr = c.to_int(r.get("USUARIO_RESOLVIDO"))
                yield (
                    fid,
                    reg if reg in self.registros else None,
                    doc if doc in self.documentos else None,
                    mot if mot in self.motivos else None,
                    c.to_dt(r.get("DATA")), usu if usu in self.usuarios else None,
                    c.txt(r.get("COMENTARIO")), c.sn_bool(r.get("RESOLVIDO"), False),
                    c.to_dt(r.get("DATA_RESOLVIDO")), usr if usr in self.usuarios else None,
                    c.txt(r.get("COMENTARIO_RESOLVIDO")),
                )

        self._copy(
            "refugo",
            ["id", "registro_id", "documento_id", "motivo_id", "data", "usuario_id",
             "comentario", "resolvido", "data_resolvido", "usuario_resolvido_id",
             "comentario_resolvido"],
            linhas(),
        )

    # ---------------------------------------------------------------- sequences
    def reset_sequences(self) -> None:
        tabelas = [
            "grupo", "tipo_documento", "tipo_documento_pagina", "indice_original",
            "indice_apos_1999", "motivo", "volume_storage", "usuario", "parametro_usuario",
            "registro", "documento", "refugo",
        ]
        with self.conn.cursor() as cur:
            for t in tabelas:
                cur.execute(f"SELECT COALESCE(max(id), 0) FROM {t}")
                maxid = cur.fetchone()[0]
                if maxid:
                    cur.execute(
                        "SELECT setval(pg_get_serial_sequence(%s, 'id'), %s)", (t, maxid)
                    )
        self.conn.commit()

    # --------------------------------------------------------------------- run
    def load_all(self) -> None:
        self.load_grupo()
        self.load_tipo_documento()
        self.load_tipo_documento_pagina()
        self.load_grupo_tipo_documento()
        self._load_indice("INDICE_ORIGINAL", "indice_original", self.indices_orig)
        self._load_indice("INDICE_APOS_1999", "indice_apos_1999", self.indices_apos)
        self.load_motivo()
        self.load_volume_storage()
        self.load_parametro()
        self.load_usuario()
        self.load_parametro_usuario()
        self.load_registro()
        self.load_documento()
        self.load_documento_legado()
        self.load_refugo()
        self.reset_sequences()
