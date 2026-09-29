"""Consulta de registros (Painel de Manipulação) e anexação de documentos."""
from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentUsuario, SessionDep
from app.schemas.consulta import CriarDocumento, DocumentoOut, RegistroBuscaOut
from app.services import anexacao_service, consulta_service

router = APIRouter(prefix="/registros", tags=["registros"])


@router.get("", response_model=list[RegistroBuscaOut])
def buscar(
    db: SessionDep,
    _usuario: CurrentUsuario,
    lote: str | None = None,
    contrato: int | None = None,
    registro_id: int | None = None,
    limite: int = 100,
) -> list[RegistroBuscaOut]:
    """Busca por lote/contrato/id; devolve nº de documentos e o cessionário (via gateway)."""
    return consulta_service.buscar_registros(
        db, lote=lote, contrato=contrato, registro_id=registro_id, limite=limite
    )


@router.get("/{registro_id}/documentos", response_model=list[DocumentoOut])
def documentos(registro_id: int, db: SessionDep, _usuario: CurrentUsuario) -> list[DocumentoOut]:
    return consulta_service.listar_documentos(db, registro_id)


@router.post("/{registro_id}/documentos", response_model=DocumentoOut, status_code=status.HTTP_201_CREATED)
def criar_documento(
    registro_id: int, dados: CriarDocumento, db: SessionDep, usuario: CurrentUsuario
) -> DocumentoOut:
    doc = anexacao_service.criar_documento(
        db, usuario, registro_id,
        tipo_doc_id=dados.tipo_doc_id, nr_folha=dados.nr_folha,
        total_folhas=dados.total_folhas, face=dados.face, pasta=dados.pasta,
    )
    return DocumentoOut(
        id=doc.id, tipo_doc_id=doc.tipo_doc_id,
        tipo_descricao=doc.tipo.descricao if doc.tipo else None,
        nr_folha=doc.nr_folha, total_folhas=doc.total_folhas, face=doc.face,
        refugada=doc.refugada, qtde_assinaturas=0, qtde_comentarios=0,
    )
