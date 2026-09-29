"""Parâmetros globais (linha única) — visualizar e editar (admin)."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import AdminUsuario, SessionDep

router = APIRouter(prefix="/parametros", tags=["cadastros"])

_COLUNAS = [
    "volume_gravacao_id",
    "volume_backup_id",
    "volume_thumbnail_id",
    "locacao_atual",
    "gravacao_datacenter",
    "backup_datacenter",
    "integracao_modo",
    "config",
]


def _obter(db: SessionDep) -> dict[str, Any]:
    row = (
        db.execute(
            text(
                "SELECT volume_gravacao_id, volume_backup_id, volume_thumbnail_id, locacao_atual, "
                "gravacao_datacenter, backup_datacenter, integracao_modo::text AS integracao_modo, "
                "config FROM parametro WHERE id = true"
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row else {c: None for c in _COLUNAS}


@router.get("")
def obter(db: SessionDep, _admin: AdminUsuario) -> dict[str, Any]:
    return _obter(db)


@router.put("")
def atualizar(dados: dict[str, Any], db: SessionDep, _admin: AdminUsuario) -> dict[str, Any]:
    sets: list[str] = []
    params: dict[str, Any] = {}
    for coluna, valor in dados.items():
        if coluna not in _COLUNAS:
            continue
        if coluna == "integracao_modo":
            sets.append(f"{coluna} = :{coluna}::integracao_modo")
        elif coluna == "config":
            sets.append(f"{coluna} = :{coluna}::jsonb")
            valor = json.dumps(valor)
        else:
            sets.append(f"{coluna} = :{coluna}")
        params[coluna] = valor

    db.execute(text("INSERT INTO parametro (id) VALUES (true) ON CONFLICT (id) DO NOTHING"))
    if sets:
        db.execute(text(f"UPDATE parametro SET {', '.join(sets)} WHERE id = true"), params)
    db.commit()
    return _obter(db)
