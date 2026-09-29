"""Endpoints de documento: upload do arquivo base, assinatura A1 e consulta de assinaturas."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status

from app.api.deps import CurrentUsuario, SessionDep
from app.models import ArquivoPapel, Documento
from app.schemas.assinatura import AssinarRequest, AssinaturaOut
from app.schemas.consulta import ComentarioRequest
from app.services import anexacao_service, assinatura_service, storage

router = APIRouter(prefix="/documentos", tags=["documentos"])


def _ext(nome: str | None) -> str | None:
    if nome and "." in nome:
        return nome.rsplit(".", 1)[-1].lower()
    return None


@router.post("/{documento_id}/arquivo", status_code=status.HTTP_201_CREATED)
async def enviar_arquivo(
    documento_id: int, db: SessionDep, usuario: CurrentUsuario, file: UploadFile = File(...)
) -> dict:
    """Anexa/atualiza o arquivo base (papel=full) do documento."""
    if db.get(Documento, documento_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado")
    conteudo = await file.read()
    arq = storage.guardar(
        db, ArquivoPapel.full, conteudo, documento_id=documento_id,
        extensao=_ext(file.filename), mime=file.content_type,
        created_by=usuario.id, nome_original=file.filename,
    )
    return {
        "arquivo_id": arq.id,
        "uuid": arq.uuid,
        "checksum_sha256": arq.checksum_sha256,
        "tamanho_bytes": arq.tamanho_bytes,
    }


@router.post("/{documento_id}/assinar", response_model=AssinaturaOut, status_code=status.HTTP_201_CREATED)
def assinar(
    documento_id: int, dados: AssinarRequest, db: SessionDep, usuario: CurrentUsuario
) -> AssinaturaOut:
    assinatura = assinatura_service.assinar_documento(db, usuario, documento_id, dados.certificado_id)
    return AssinaturaOut.model_validate(assinatura)


@router.post("/{documento_id}/comentario", status_code=status.HTTP_201_CREATED)
def comentario(
    documento_id: int, dados: ComentarioRequest, db: SessionDep, usuario: CurrentUsuario
) -> dict:
    """Adiciona comentário/particularidade (motivo opcional) e/ou refuga o documento."""
    refugo = anexacao_service.adicionar_comentario(
        db, usuario, documento_id,
        motivo_id=dados.motivo_id, comentario=dados.comentario, refugar=dados.refugar,
    )
    return {
        "id": refugo.id,
        "documento_id": refugo.documento_id,
        "motivo_id": refugo.motivo_id,
        "comentario": refugo.comentario,
        "refugada": dados.refugar,
    }


@router.get("/{documento_id}/assinaturas")
def listar_assinaturas(documento_id: int, db: SessionDep, _usuario: CurrentUsuario) -> dict:
    """Selo 'X assinaturas' + detalhes (req. 6)."""
    return assinatura_service.listar_assinaturas(db, documento_id)


@router.get("/{documento_id}/assinado")
def baixar_assinado(documento_id: int, db: SessionDep, _usuario: CurrentUsuario) -> Response:
    pdf = assinatura_service.pdf_assinado(db, documento_id)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="documento_{documento_id}_assinado.pdf"'},
    )
