"""DTOs de certificado A1 e assinatura."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import AssinaturaStatus


class CertificadoOut(BaseModel):
    id: int
    nome_titular: str | None
    cpf_cnpj: str | None
    numero_serie: str | None
    emissor: str | None
    validade_inicio: datetime | None
    validade_fim: datetime | None
    ativo: bool

    model_config = {"from_attributes": True}


class AssinarRequest(BaseModel):
    certificado_id: int


class AssinaturaOut(BaseModel):
    id: int
    documento_id: int
    usuario_id: int
    ordem: int
    carimbo_pagina: int | None
    carimbo_nova_folha: bool
    status: AssinaturaStatus
    hash_documento: str | None
    assinado_em: datetime

    model_config = {"from_attributes": True}
