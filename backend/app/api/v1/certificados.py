"""Endpoints de certificado A1 (.pfx) do usuário."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile, status

from app.api.deps import CurrentUsuario, SessionDep
from app.schemas.assinatura import CertificadoOut
from app.services import certificado_service

router = APIRouter(prefix="/certificados", tags=["certificados"])


@router.post("", response_model=CertificadoOut, status_code=status.HTTP_201_CREATED)
async def enviar_certificado(
    db: SessionDep,
    usuario: CurrentUsuario,
    file: UploadFile = File(..., description="Arquivo .pfx / PKCS#12"),
    senha: str = Form(..., description="Senha do certificado"),
) -> CertificadoOut:
    conteudo = await file.read()
    cert = certificado_service.cadastrar_certificado(db, usuario, conteudo, senha)
    return CertificadoOut.model_validate(cert)


@router.get("", response_model=list[CertificadoOut])
def listar_certificados(db: SessionDep, usuario: CurrentUsuario) -> list[CertificadoOut]:
    return [
        CertificadoOut.model_validate(c)
        for c in certificado_service.listar_certificados(db, usuario)
    ]
