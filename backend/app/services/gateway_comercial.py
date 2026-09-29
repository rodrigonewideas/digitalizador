"""Integração com o sistema comercial do cliente (pdv_bonfim).

Resolve dados de **cessionário/contrato** que NÃO pertencem ao Digitalizador
(nome do cliente, tipo de terreno, falecido). Adaptador plugável: hoje leitura
direta do banco (a configurar), amanhã via API REST — escolhido por
`parametro.integracao_modo`. Ver docs/01 §3.9.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class CessionarioInfo:
    contrato: int | None = None
    nome_cessionario: str | None = None
    cpf: str | None = None
    tipo_terreno: str | None = None
    falecido: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class GatewayComercial(Protocol):
    def resolver_contrato(self, contrato: int | None) -> CessionarioInfo | None: ...
    def resolver_por_lote(self, lote: str) -> list[CessionarioInfo]: ...


class DbGateway:
    """Leitura direta do banco do cliente (pdv_bonfim).

    A conexão ainda não está configurada — retorna vazio (placeholder). Quando o
    acesso for liberado, este método consulta o banco comercial e preenche os dados.
    """

    def resolver_contrato(self, contrato: int | None) -> CessionarioInfo | None:
        return None

    def resolver_por_lote(self, lote: str) -> list[CessionarioInfo]:
        return []


class ApiGateway:
    """Consumo da API REST do sistema comercial (futuro próximo)."""

    def resolver_contrato(self, contrato: int | None) -> CessionarioInfo | None:
        return None

    def resolver_por_lote(self, lote: str) -> list[CessionarioInfo]:
        return []


def get_gateway(db: Session) -> GatewayComercial:
    modo = db.scalar(text("SELECT integracao_modo::text FROM parametro LIMIT 1")) or "direct_db"
    return ApiGateway() if modo == "api" else DbGateway()
