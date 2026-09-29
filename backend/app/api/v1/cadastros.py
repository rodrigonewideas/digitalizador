"""Rotas CRUD das tabelas de cadastro (admin)."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.crud import crud_router
from app.models import (
    Caracteristica,
    Grupo,
    IndiceApos1999,
    IndiceOriginal,
    Motivo,
    TipoDocumento,
)
from app.schemas.consulta import MotivoOut, TipoDocumentoOut
from app.schemas.tabelas import (
    CaracteristicaCreate,
    CaracteristicaOut,
    CaracteristicaUpdate,
    DescricaoCreate,
    DescricaoOut,
    DescricaoUpdate,
    GrupoCreate,
    GrupoOut,
    GrupoUpdate,
    TipoDocumentoCreate,
    TipoDocumentoUpdate,
)

router = APIRouter()

router.include_router(
    crud_router(
        nome="motivo", prefix="/motivos", model=Motivo,
        out_schema=MotivoOut, create_schema=DescricaoCreate, update_schema=DescricaoUpdate,
        ordem=Motivo.descricao,
    )
)
router.include_router(
    crud_router(
        nome="indice_original", prefix="/indices-original", model=IndiceOriginal,
        out_schema=DescricaoOut, create_schema=DescricaoCreate, update_schema=DescricaoUpdate,
        ordem=IndiceOriginal.descricao,
    )
)
router.include_router(
    crud_router(
        nome="indice_apos_1999", prefix="/indices-apos-1999", model=IndiceApos1999,
        out_schema=DescricaoOut, create_schema=DescricaoCreate, update_schema=DescricaoUpdate,
        ordem=IndiceApos1999.descricao,
    )
)
router.include_router(
    crud_router(
        nome="grupo", prefix="/grupos", model=Grupo,
        out_schema=GrupoOut, create_schema=GrupoCreate, update_schema=GrupoUpdate,
        ordem=Grupo.descricao,
    )
)
router.include_router(
    crud_router(
        nome="caracteristica", prefix="/caracteristicas", model=Caracteristica,
        out_schema=CaracteristicaOut, create_schema=CaracteristicaCreate,
        update_schema=CaracteristicaUpdate, ordem=Caracteristica.nome,
    )
)
router.include_router(
    crud_router(
        nome="tipo_documento", prefix="/tipos-documento", model=TipoDocumento,
        out_schema=TipoDocumentoOut, create_schema=TipoDocumentoCreate,
        update_schema=TipoDocumentoUpdate, ordem=TipoDocumento.descricao,
    )
)
