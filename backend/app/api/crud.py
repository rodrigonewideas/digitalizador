"""Fábrica de rotas CRUD para tabelas de cadastro (admin).

Gera GET/POST/PUT/DELETE padronizados para um modelo simples, com tratamento de
duplicidade e de "registro em uso" (FK). Uso em app/api/v1/cadastros.py.

NB: NÃO use `from __future__ import annotations` aqui — a fábrica cria funções com
anotações de tipo DINÂMICAS (`dados: create_schema`) que o FastAPI precisa resolver
como classes reais, não como strings/ForwardRef.
"""
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AdminUsuario, SessionDep
from app.core.database import Base


def crud_router(
    *,
    nome: str,
    prefix: str,
    model: type[Base],
    out_schema: type[BaseModel],
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    ordem: Any | None = None,
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["cadastros"])
    coluna_ordem = ordem if ordem is not None else model.id  # type: ignore[attr-defined]

    @router.get("", response_model=list[out_schema], operation_id=f"{nome}_listar")
    def listar(db: SessionDep, _admin: AdminUsuario) -> Any:
        return list(db.scalars(select(model).order_by(coluna_ordem)))

    @router.post(
        "",
        response_model=out_schema,
        status_code=status.HTTP_201_CREATED,
        operation_id=f"{nome}_criar",
    )
    def criar(dados: create_schema, db: SessionDep, _admin: AdminUsuario) -> Any:  # type: ignore[valid-type]
        obj = model(**dados.model_dump())  # type: ignore[call-arg]
        db.add(obj)
        _commit(db, "Registro duplicado ou inválido")
        db.refresh(obj)
        return obj

    @router.put("/{item_id}", response_model=out_schema, operation_id=f"{nome}_atualizar")
    def atualizar(
        item_id: int, dados: update_schema, db: SessionDep, _admin: AdminUsuario  # type: ignore[valid-type]
    ) -> Any:
        obj = db.get(model, item_id)
        if obj is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Registro não encontrado")
        for campo, valor in dados.model_dump(exclude_unset=True).items():  # type: ignore[attr-defined]
            setattr(obj, campo, valor)
        _commit(db, "Valor duplicado ou inválido")
        db.refresh(obj)
        return obj

    @router.delete(
        "/{item_id}", status_code=status.HTTP_204_NO_CONTENT, operation_id=f"{nome}_excluir"
    )
    def excluir(item_id: int, db: SessionDep, _admin: AdminUsuario) -> None:
        obj = db.get(model, item_id)
        if obj is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Registro não encontrado")
        db.delete(obj)
        _commit(db, "Registro em uso; não pode ser excluído.")

    return router


def _commit(db: SessionDep, msg_conflito: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, msg_conflito) from exc
