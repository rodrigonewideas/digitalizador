"""Integração com o sistema comercial do cliente (solution / PDV_BONFIM).

Resolve dados de **terreno(lote)/cessionário** que NÃO pertencem ao Digitalizador
(nº do terreno, tipo de terreno, cessionários) e que o legado buscava na base
comercial (alias `dbsolution`). Adaptador plugável escolhido por
`parametro.integracao_modo`: hoje leitura direta do Firebird (`direct_db`),
amanhã via API REST (`api`). Ver docs/01 §3.9.

Regras de segurança: acesso **somente leitura** ao banco do cliente. Se a conexão
não estiver configurada/acessível, os métodos degradam para vazio (fail-safe) —
a consulta por contrato/registro continua funcionando normalmente.

SQL de origem (extraído da fonte Delphi u_viConsultaDoc.dfm):
    select c.contrato, c.nr_contrato, t.codigo, t.razao as cessionario,
           c.nr_terreno, tt.descr as tipo_terreno
    from contrato c
    join contrato_titular ct on c.contrato = ct.contrato
    join titular t           on ct.titular  = t.codigo
    join tipo_terreno tt     on tt.tipo_terreno = c.tipo_terreno
    where c.contrato = :id_contrato
"""
from __future__ import annotations

import logging
import time
import unicodedata
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings

log = logging.getLogger(__name__)

# Cache do índice contrato->cessionário p/ busca por nome (evita varrer o FB a cada tecla)
_CACHE_TTL_S = 600
_cache_cessionarios: tuple[float, list[tuple[int, str]]] | None = None


@dataclass
class CessionarioInfo:
    contrato: int | None = None
    nr_contrato: str | None = None
    nr_terreno: str | None = None
    nome_cessionario: str | None = None
    cessionarios: list[str] | None = None
    cpf: str | None = None
    tipo_terreno: str | None = None
    falecido: str | None = None
    dt_venda: str | None = None
    vendedor: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class GatewayComercial(Protocol):
    def contratos_por_terreno(self, terreno: str | None) -> list[int]: ...
    def contratos_por_cessionario(self, nome: str | None) -> list[int]: ...
    def resolver_contrato(self, contrato: int | None) -> CessionarioInfo | None: ...
    def resolver_contratos(self, contratos: list[int]) -> dict[int, CessionarioInfo]: ...
    def resolver_por_lote(self, lote: str | None) -> list[CessionarioInfo]: ...


def _txt(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _int(v: Any) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _data(v: Any) -> str | None:
    """Data do Firebird -> ISO (yyyy-mm-dd)."""
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return None


def _norm(s: str) -> str:
    """Sem acentos, maiúsculas — p/ busca de nome insensível a caixa/acento."""
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").upper()


class DbGateway:
    """Leitura direta do banco comercial do cliente (Firebird, somente SELECT)."""

    def __init__(self, settings: Settings) -> None:
        self._s = settings

    def _connect(self):  # type: ignore[no-untyped-def]
        import firebirdsql  # import tardio: só carrega se a integração estiver em uso

        s = self._s
        return firebirdsql.connect(
            host=s.pdv_fb_host,
            port=s.pdv_fb_port,
            database=s.pdv_fb_database,
            user=s.pdv_fb_user,
            password=s.pdv_fb_password,
            charset=s.pdv_fb_charset,
        )

    def contratos_por_terreno(self, terreno: str | None) -> list[int]:
        terreno = _txt(terreno)
        if not terreno or not self._s.pdv_habilitado:
            return []
        sql = "select c.contrato from contrato c where c.nr_terreno = ?"
        try:
            with closing(self._connect()) as con, closing(con.cursor()) as cur:
                cur.execute(sql, (terreno,))
                return [i for i in (_int(r[0]) for r in cur.fetchall()) if i is not None]
        except Exception as e:  # noqa: BLE001 - integração externa: degrada, não derruba
            log.warning("PDV contratos_por_terreno(%r) falhou: %s", terreno, e)
            return []

    def contratos_por_cessionario(self, nome: str | None) -> list[int]:
        """Contratos cujo cessionário contém o nome (sem acento/caixa). Índice com cache."""
        global _cache_cessionarios
        nome = _txt(nome)
        if not nome or len(nome) < 3 or not self._s.pdv_habilitado:
            return []
        agora = time.monotonic()
        if _cache_cessionarios is None or agora - _cache_cessionarios[0] > _CACHE_TTL_S:
            sql = ("select ct.contrato, t.razao from contrato_titular ct "
                   "join titular t on t.codigo = ct.titular")
            try:
                with closing(self._connect()) as con, closing(con.cursor()) as cur:
                    cur.execute(sql)
                    indice = [
                        (cid, _norm(rz))
                        for contrato, razao in cur.fetchall()
                        if (cid := _int(contrato)) is not None and (rz := _txt(razao))
                    ]
            except Exception as e:  # noqa: BLE001 - integração externa: degrada, não derruba
                log.warning("PDV contratos_por_cessionario(%r) falhou: %s", nome, e)
                return []
            _cache_cessionarios = (agora, indice)
        alvo = _norm(nome)
        vistos: set[int] = set()
        achados: list[int] = []
        for cid, razao in _cache_cessionarios[1]:
            if alvo in razao and cid not in vistos:
                vistos.add(cid)
                achados.append(cid)
        return achados

    def resolver_contratos(self, contratos: list[int]) -> dict[int, CessionarioInfo]:
        ids = sorted({i for i in (_int(c) for c in contratos) if i is not None})
        if not ids or not self._s.pdv_habilitado:
            return {}
        marcadores = ",".join("?" * len(ids))
        sql = (
            "select c.contrato, c.nr_contrato, c.nr_terreno, tt.descr, t.razao, "
            "ct.resp_pgto, ct.dt_venda, v.nome "
            "from contrato c "
            "left join tipo_terreno tt on tt.tipo_terreno = c.tipo_terreno "
            "left join vendedor v on v.vendedor = c.vendedor "
            "left join contrato_titular ct on ct.contrato = c.contrato "
            "left join titular t on t.codigo = ct.titular "
            f"where c.contrato in ({marcadores})"
        )
        try:
            with closing(self._connect()) as con, closing(con.cursor()) as cur:
                cur.execute(sql, ids)
                linhas = cur.fetchall()
        except Exception as e:  # noqa: BLE001 - integração externa: degrada, não derruba
            log.warning("PDV resolver_contratos(%d ids) falhou: %s", len(ids), e)
            return {}

        infos: dict[int, CessionarioInfo] = {}
        nomes: dict[int, list[str]] = {}
        for contrato, nr_contrato, nr_terreno, tipo_terreno, cessionario, resp, dtv, vend in linhas:
            cid = _int(contrato)
            if cid is None:
                continue
            if cid not in infos:
                infos[cid] = CessionarioInfo(
                    contrato=cid,
                    nr_contrato=_txt(nr_contrato),
                    nr_terreno=_txt(nr_terreno),
                    tipo_terreno=_txt(tipo_terreno),
                    vendedor=_txt(vend),
                )
                nomes[cid] = []
            info = infos[cid]
            nome = _txt(cessionario)
            if nome and nome not in nomes[cid]:
                nomes[cid].append(nome)
            # titular responsável pelo pagamento define o nome principal e a data da venda
            if (_txt(resp) or "").upper() == "S":
                if nome:
                    info.nome_cessionario = nome
                info.dt_venda = info.dt_venda or _data(dtv)
            info.dt_venda = info.dt_venda or _data(dtv)
        for cid, info in infos.items():
            info.cessionarios = nomes[cid] or None
            if not info.nome_cessionario:
                info.nome_cessionario = nomes[cid][0] if nomes[cid] else None
        return infos

    def resolver_contrato(self, contrato: int | None) -> CessionarioInfo | None:
        cid = _int(contrato)
        if cid is None:
            return None
        return self.resolver_contratos([cid]).get(cid)

    def resolver_por_lote(self, lote: str | None) -> list[CessionarioInfo]:
        contratos = self.contratos_por_terreno(lote)
        if not contratos:
            return []
        infos = self.resolver_contratos(contratos)
        return [infos[c] for c in contratos if c in infos]


class ApiGateway:
    """Consumo da API REST do sistema comercial (futuro próximo). Ainda inativo."""

    def __init__(self, settings: Settings) -> None:
        self._s = settings

    def contratos_por_terreno(self, terreno: str | None) -> list[int]:
        return []

    def contratos_por_cessionario(self, nome: str | None) -> list[int]:
        return []

    def resolver_contratos(self, contratos: list[int]) -> dict[int, CessionarioInfo]:
        return {}

    def resolver_contrato(self, contrato: int | None) -> CessionarioInfo | None:
        return None

    def resolver_por_lote(self, lote: str | None) -> list[CessionarioInfo]:
        return []


def get_gateway(db: Session) -> GatewayComercial:
    settings = get_settings()
    modo = db.scalar(text("SELECT integracao_modo::text FROM parametro LIMIT 1")) or "direct_db"
    return ApiGateway(settings) if modo == "api" else DbGateway(settings)
