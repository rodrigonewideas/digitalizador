"""Schemas das tabelas de cadastro (CRUD)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

_cfg = {"from_attributes": True}


# --- Descrição simples (motivo, índices) ---
class DescricaoOut(BaseModel):
    id: int
    descricao: str
    model_config = _cfg


class DescricaoCreate(BaseModel):
    descricao: str = Field(min_length=1, max_length=70)


class DescricaoUpdate(BaseModel):
    descricao: str | None = Field(default=None, min_length=1, max_length=70)


# --- Grupo ---
class GrupoOut(BaseModel):
    id: int
    descricao: str
    ativo: bool
    created_at: datetime | None = None
    model_config = _cfg


class GrupoCreate(BaseModel):
    descricao: str = Field(min_length=1, max_length=40)
    ativo: bool = True


class GrupoUpdate(BaseModel):
    descricao: str | None = Field(default=None, min_length=1, max_length=40)
    ativo: bool | None = None


# --- Característica ---
class CaracteristicaOut(BaseModel):
    id: int
    nome: str
    ativo: bool
    model_config = _cfg


class CaracteristicaCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=20)
    ativo: bool = True


class CaracteristicaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=20)
    ativo: bool | None = None


# --- Tipo de documento ---
class TipoDocumentoCreate(BaseModel):
    descricao: str = Field(min_length=1, max_length=20)
    descricao_detalhada: str | None = Field(default=None, max_length=100)
    frente_verso: bool = False
    indicacao_frente: str | None = Field(default=None, max_length=50)
    qtde_folhas: int = Field(default=1, ge=1)
    pagina_inicial: int | None = None
    ativo: bool = True


class TipoDocumentoUpdate(BaseModel):
    descricao: str | None = Field(default=None, min_length=1, max_length=20)
    descricao_detalhada: str | None = Field(default=None, max_length=100)
    frente_verso: bool | None = None
    indicacao_frente: str | None = Field(default=None, max_length=50)
    qtde_folhas: int | None = Field(default=None, ge=1)
    pagina_inicial: int | None = None
    ativo: bool | None = None
