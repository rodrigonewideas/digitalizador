"""DTOs de consulta e anexação de documentos."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TipoDocumentoOut(BaseModel):
    id: int
    descricao: str
    descricao_detalhada: str | None
    frente_verso: bool
    indicacao_frente: str | None
    qtde_folhas: int
    pagina_inicial: int | None
    ativo: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class MotivoOut(BaseModel):
    id: int
    descricao: str

    model_config = {"from_attributes": True}


class RegistroBuscaOut(BaseModel):
    id: int
    contrato: int | None
    lote: str | None
    titular: int | None
    sepultado: int | None
    qtde_documentos: int
    qtde_refugados: int
    cessionario: dict | None  # do GatewayComercial (nome/cpf/tipo_terreno/falecido)


class DocumentoOut(BaseModel):
    id: int
    tipo_doc_id: int | None
    tipo_descricao: str | None
    nr_folha: int | None
    total_folhas: int | None
    face: str | None
    refugada: bool
    qtde_assinaturas: int
    qtde_comentarios: int


class CriarDocumento(BaseModel):
    tipo_doc_id: int | None = None
    nr_folha: int | None = Field(default=None, ge=0)
    total_folhas: int | None = Field(default=None, ge=0)
    face: str | None = Field(default=None, pattern="^[FV]$")
    pasta: str | None = Field(default=None, max_length=5)


class ComentarioRequest(BaseModel):
    motivo_id: int | None = None
    comentario: str | None = Field(default=None, max_length=200)
    refugar: bool = False
