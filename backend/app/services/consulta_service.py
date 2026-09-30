"""Consulta de registros/documentos (Painel de Manipulação)."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Assinatura, AssinaturaStatus, Documento, Refugo, Registro
from app.services.gateway_comercial import get_gateway


def buscar_registros(
    db: Session,
    *,
    lote: str | None = None,
    contrato: int | None = None,
    registro_id: int | None = None,
    limite: int = 100,
) -> list[dict]:
    if not any([lote, contrato, registro_id]):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Informe ao menos um filtro: lote, contrato ou registro_id.",
        )
    gw = get_gateway(db)
    q = select(Registro)
    if registro_id:
        q = q.where(Registro.id == registro_id)
    if contrato:
        q = q.where(Registro.contrato == contrato)
    if lote:
        # "Nº do lote" = nr_terreno no sistema comercial (legado): resolve o terreno
        # para os contratos e filtra os registros do digitalizador por eles.
        contratos = gw.contratos_por_terreno(str(lote))
        if not contratos:
            return []
        q = q.where(Registro.contrato.in_(contratos))
    registros = list(db.scalars(q.order_by(Registro.id).limit(limite)))
    ids = [r.id for r in registros]

    docs = _contagem(db, Documento.registro_id, ids)
    refug = _contagem(db, Documento.registro_id, ids, Documento.refugada.is_(True))
    infos = gw.resolver_contratos([r.contrato for r in registros if r.contrato is not None])

    resultado = []
    for r in registros:
        info = infos.get(r.contrato) if r.contrato is not None else None
        resultado.append(
            {
                "id": r.id,
                "contrato": r.contrato,
                "lote": r.lote,
                "titular": r.titular,
                "sepultado": r.sepultado,
                "qtde_documentos": docs.get(r.id, 0),
                "qtde_refugados": refug.get(r.id, 0),
                "cessionario": info.to_dict() if info else None,
            }
        )
    return resultado


def listar_documentos(db: Session, registro_id: int) -> list[dict]:
    if db.get(Registro, registro_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Registro não encontrado")
    docs = list(
        db.scalars(
            select(Documento)
            .where(Documento.registro_id == registro_id)
            .order_by(Documento.nr_folha, Documento.id)
        )
    )
    ids = [d.id for d in docs]
    assinaturas = _contagem(
        db, Assinatura.documento_id, ids, Assinatura.status != AssinaturaStatus.revogada
    )
    comentarios = _contagem(db, Refugo.documento_id, ids)
    return [
        {
            "id": d.id,
            "tipo_doc_id": d.tipo_doc_id,
            "tipo_descricao": d.tipo.descricao if d.tipo else None,
            "nr_folha": d.nr_folha,
            "total_folhas": d.total_folhas,
            "face": d.face,
            "refugada": d.refugada,
            "qtde_assinaturas": assinaturas.get(d.id, 0),
            "qtde_comentarios": comentarios.get(d.id, 0),
        }
        for d in docs
    ]


def _contagem(db: Session, coluna, ids: list[int], *filtros) -> dict[int, int]:
    if not ids:
        return {}
    stmt = select(coluna, func.count()).where(coluna.in_(ids), *filtros).group_by(coluna)
    return {chave: total for chave, total in db.execute(stmt).all()}
