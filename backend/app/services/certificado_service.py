"""Gestão de certificados A1 (.pfx / PKCS#12) do usuário.

O .pfx e a senha são guardados **cifrados** em repouso. Metadados (titular, validade,
série, emissor) são extraídos para exibição e controle.
"""
from __future__ import annotations

from datetime import timezone

from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.models import Arquivo, ArquivoPapel, Usuario, UsuarioCertificado


def _cn(nome) -> str | None:
    try:
        attrs = nome.get_attributes_for_oid(NameOID.COMMON_NAME)
        return attrs[0].value if attrs else None
    except Exception:  # noqa: BLE001
        return None


def _aware(dt):
    return dt.replace(tzinfo=timezone.utc) if dt and dt.tzinfo is None else dt


def cadastrar_certificado(
    db: Session, usuario: Usuario, pfx_bytes: bytes, senha: str
) -> UsuarioCertificado:
    try:
        chave, cert, _extras = pkcs12.load_key_and_certificates(pfx_bytes, senha.encode())
    except Exception as exc:  # noqa: BLE001 - senha errada ou .pfx inválido
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Certificado inválido ou senha incorreta") from exc
    if cert is None or chave is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "PKCS#12 sem chave/certificado")

    # validade (cryptography >=42 expõe *_utc)
    validade_ini = _aware(getattr(cert, "not_valid_before_utc", None) or cert.not_valid_before)
    validade_fim = _aware(getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after)
    titular = _cn(cert.subject)
    emissor = _cn(cert.issuer)

    # guarda o .pfx cifrado como arquivo (papel=certificado)
    arquivo = _guardar_pfx_cifrado(db, usuario, pfx_bytes)

    certificado = UsuarioCertificado(
        usuario_id=usuario.id,
        nome_titular=titular,
        cpf_cnpj=_cpf_do_cn(titular),
        arquivo_id=arquivo.id,
        senha_pfx_cifrada=security.cifrar(senha.encode()),
        numero_serie=format(cert.serial_number, "x"),
        emissor=emissor,
        validade_inicio=validade_ini,
        validade_fim=validade_fim,
        ativo=True,
    )
    db.add(certificado)
    db.commit()
    db.refresh(certificado)
    return certificado


def _guardar_pfx_cifrado(db: Session, usuario: Usuario, pfx_bytes: bytes) -> Arquivo:
    from app.services import storage

    return storage.guardar(
        db,
        ArquivoPapel.certificado,
        security.cifrar(pfx_bytes),  # cifrado em repouso
        extensao="pfx.enc",
        mime="application/octet-stream",
        created_by=usuario.id,
    )


def _cpf_do_cn(cn: str | None) -> str | None:
    # certificados ICP-Brasil costumam trazer "NOME:CPF" no CN
    if cn and ":" in cn:
        cauda = cn.rsplit(":", 1)[-1].strip()
        if cauda.isdigit():
            return cauda
    return None


def listar_certificados(db: Session, usuario: Usuario) -> list[UsuarioCertificado]:
    return list(
        db.scalars(
            select(UsuarioCertificado)
            .where(UsuarioCertificado.usuario_id == usuario.id)
            .order_by(UsuarioCertificado.id.desc())
        )
    )


def obter_certificado(db: Session, usuario: Usuario, certificado_id: int) -> UsuarioCertificado:
    cert = db.get(UsuarioCertificado, certificado_id)
    if cert is None or cert.usuario_id != usuario.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Certificado não encontrado")
    if not cert.ativo:
        raise HTTPException(status.HTTP_409_CONFLICT, "Certificado inativo")
    return cert


def carregar_pfx(db: Session, certificado: UsuarioCertificado) -> tuple[bytes, str]:
    """Devolve (pfx_bytes, senha) decifrados para uso na assinatura."""
    from app.services import storage

    arquivo = db.get(Arquivo, certificado.arquivo_id)
    pfx_cifrado = storage.ler(db, arquivo)
    pfx = security.decifrar(pfx_cifrado)
    senha = security.decifrar(certificado.senha_pfx_cifrada).decode()
    return pfx, senha
