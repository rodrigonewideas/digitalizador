"""Anexação/ajuste de documentos e comentários/refugos."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    Documento,
    LogAuditoria,
    Motivo,
    Refugo,
    Registro,
    TipoDocumento,
    Usuario,
)


def criar_documento(
    db: Session,
    usuario: Usuario,
    registro_id: int,
    *,
    tipo_doc_id: int | None = None,
    nr_folha: int | None = None,
    total_folhas: int | None = None,
    face: str | None = None,
    pasta: str | None = None,
) -> Documento:
    if db.get(Registro, registro_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Registro não encontrado")
    if tipo_doc_id is not None and db.get(TipoDocumento, tipo_doc_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Tipo de documento inexistente")

    doc = Documento(
        registro_id=registro_id,
        tipo_doc_id=tipo_doc_id,
        nr_folha=nr_folha,
        total_folhas=total_folhas,
        face=face,
        pasta=pasta,
        refugada=False,
        cadastro=datetime.now(timezone.utc),
    )
    db.add(doc)
    db.add(
        LogAuditoria(
            usuario_id=usuario.id, acao="documento_anexado", entidade="documento",
            detalhe={"registro_id": registro_id, "tipo_doc_id": tipo_doc_id},
        )
    )
    db.commit()
    db.refresh(doc)
    return doc


def adicionar_comentario(
    db: Session,
    usuario: Usuario,
    documento_id: int,
    *,
    motivo_id: int | None = None,
    comentario: str | None = None,
    refugar: bool = False,
) -> Refugo:
    doc = db.get(Documento, documento_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado")
    if motivo_id is not None and db.get(Motivo, motivo_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Motivo inexistente")
    if not comentario and motivo_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Informe um motivo e/ou comentário")

    refugo = Refugo(
        registro_id=doc.registro_id,
        documento_id=doc.id,
        motivo_id=motivo_id,
        usuario_id=usuario.id,
        comentario=comentario,
        resolvido=False,
    )
    db.add(refugo)
    if refugar:
        doc.refugada = True
    db.add(
        LogAuditoria(
            usuario_id=usuario.id,
            acao="documento_refugado" if refugar else "documento_comentado",
            entidade="documento", entidade_id=doc.id,
            detalhe={"motivo_id": motivo_id},
        )
    )
    db.commit()
    db.refresh(refugo)
    return refugo
