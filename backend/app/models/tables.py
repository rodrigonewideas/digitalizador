"""Modelos ORM das tabelas usadas na autenticação/acesso."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CHAR,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ArquivoPapel, AssinaturaStatus, CodigoTipo, UsuarioStatus


def _pg_enum(enum_cls: type, name: str) -> SAEnum:
    # usa o tipo ENUM já existente no banco (create_type=False)
    return SAEnum(
        enum_cls,
        name=name,
        create_type=False,
        native_enum=True,
        values_callable=lambda e: [m.value for m in e],
    )


class Grupo(Base):
    __tablename__ = "grupo"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    descricao: Mapped[str] = mapped_column(String(40))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    login: Mapped[str] = mapped_column(String, unique=True)
    nome: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String, unique=True)
    senha_hash: Mapped[str | None] = mapped_column(Text)
    email_verificado: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[UsuarioStatus] = mapped_column(
        _pg_enum(UsuarioStatus, "usuario_status"), default=UsuarioStatus.pendente
    )
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    grupo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("grupo.id"))
    tentativas_login: Mapped[int] = mapped_column(Integer, default=0)
    acesso_cancelado: Mapped[bool] = mapped_column(Boolean, default=False)
    bloqueado_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    endereco: Mapped[str | None] = mapped_column(String(100))
    cidade: Mapped[str | None] = mapped_column(String(40))
    fone_principal: Mapped[str | None] = mapped_column(String(20))
    fone_secundario: Mapped[str | None] = mapped_column(String(20))
    data_cadastro: Mapped[datetime | None] = mapped_column(Date)
    data_desligamento: Mapped[datetime | None] = mapped_column(Date)
    motivo_desligamento: Mapped[str | None] = mapped_column(String(200))
    vlr_jpg_pasta: Mapped[float | None] = mapped_column(Numeric(12, 4))
    vlr_jpg_unit: Mapped[float | None] = mapped_column(Numeric(12, 4))
    vlr_dg_pasta: Mapped[float | None] = mapped_column(Numeric(12, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    grupo: Mapped[Grupo] = relationship(lazy="joined")


class CodigoVerificacao(Base):
    __tablename__ = "codigo_verificacao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("usuario.id", ondelete="CASCADE"))
    tipo: Mapped[CodigoTipo] = mapped_column(_pg_enum(CodigoTipo, "codigo_tipo"))
    codigo_hash: Mapped[str] = mapped_column(Text)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tentativas: Mapped[int] = mapped_column(Integer, default=0)
    ip_origem: Mapped[str | None] = mapped_column(INET)
    contexto: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Sessao(Base):
    __tablename__ = "sessao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("usuario.id", ondelete="CASCADE"))
    refresh_token_hash: Mapped[str] = mapped_column(Text, unique=True)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revogado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_origem: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LogAuditoria(Base):
    __tablename__ = "log_auditoria"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("usuario.id"))
    acao: Mapped[str] = mapped_column(String(60))
    entidade: Mapped[str | None] = mapped_column(String(40))
    entidade_id: Mapped[int | None] = mapped_column(BigInteger)
    detalhe: Mapped[dict | None] = mapped_column(JSONB)
    ip_origem: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --- Domínio (subconjunto necessário à assinatura) ---------------------------
class Registro(Base):
    __tablename__ = "registro"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    titular: Mapped[int | None] = mapped_column(Integer)
    contrato: Mapped[int | None] = mapped_column(Integer)
    sepultado: Mapped[int | None] = mapped_column(Integer)
    lote: Mapped[str | None] = mapped_column(String(10))


class TipoDocumento(Base):
    __tablename__ = "tipo_documento"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    descricao: Mapped[str] = mapped_column(String(20))
    descricao_detalhada: Mapped[str | None] = mapped_column(String(100))
    frente_verso: Mapped[bool] = mapped_column(Boolean, default=False)
    indicacao_frente: Mapped[str | None] = mapped_column(String(50))
    qtde_folhas: Mapped[int] = mapped_column(Integer, default=1)
    pagina_inicial: Mapped[int | None] = mapped_column(Integer)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Motivo(Base):
    __tablename__ = "motivo"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    descricao: Mapped[str] = mapped_column(String(50))


class IndiceOriginal(Base):
    __tablename__ = "indice_original"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    descricao: Mapped[str] = mapped_column(String(70))


class IndiceApos1999(Base):
    __tablename__ = "indice_apos_1999"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    descricao: Mapped[str] = mapped_column(String(70))


class Caracteristica(Base):
    __tablename__ = "caracteristica"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nome: Mapped[str] = mapped_column(String(20))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Documento(Base):
    __tablename__ = "documento"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    registro_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("registro.id"))
    tipo_doc_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("tipo_documento.id"))
    face: Mapped[str | None] = mapped_column(CHAR(1))
    nr_folha: Mapped[int | None] = mapped_column(Integer)
    total_folhas: Mapped[int | None] = mapped_column(Integer)
    pasta: Mapped[str | None] = mapped_column(String(5))
    refugada: Mapped[bool] = mapped_column(Boolean, default=False)
    cadastro: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    registro: Mapped[Registro] = relationship(lazy="joined")
    tipo: Mapped["TipoDocumento | None"] = relationship(lazy="joined")


class Refugo(Base):
    __tablename__ = "refugo"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    registro_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("registro.id"))
    documento_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("documento.id"))
    motivo_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("motivo.id"))
    data: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    usuario_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("usuario.id"))
    comentario: Mapped[str | None] = mapped_column(String(200))
    resolvido: Mapped[bool] = mapped_column(Boolean, default=False)
    data_resolvido: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    usuario_resolvido_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("usuario.id"))
    comentario_resolvido: Mapped[str | None] = mapped_column(String(200))


# --- Storage -----------------------------------------------------------------
class VolumeStorage(Base):
    __tablename__ = "volume_storage"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nome: Mapped[str] = mapped_column(String(50))
    raiz_full: Mapped[str | None] = mapped_column(String(255))
    raiz_thumb: Mapped[str | None] = mapped_column(String(255))
    raiz_backup: Mapped[str | None] = mapped_column(String(255))
    raiz_alta: Mapped[str | None] = mapped_column(String(255))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Arquivo(Base):
    __tablename__ = "arquivo"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    uuid: Mapped[str] = mapped_column(UUID(as_uuid=False), server_default=func.gen_random_uuid())
    documento_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("documento.id"))
    papel: Mapped[ArquivoPapel] = mapped_column(_pg_enum(ArquivoPapel, "arquivo_papel"))
    volume_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("volume_storage.id"))
    object_key: Mapped[str] = mapped_column(String(255))
    nome_original: Mapped[bytes | None] = mapped_column(LargeBinary)
    extensao: Mapped[str | None] = mapped_column(String(10))
    mime: Mapped[str | None] = mapped_column(String(100))
    tamanho_bytes: Mapped[int | None] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str | None] = mapped_column(CHAR(64))
    largura_px: Mapped[int | None] = mapped_column(Integer)
    altura_px: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("usuario.id"))


# --- Assinatura A1 -----------------------------------------------------------
class UsuarioCertificado(Base):
    __tablename__ = "usuario_certificado"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("usuario.id", ondelete="CASCADE"))
    nome_titular: Mapped[str | None] = mapped_column(String(150))
    cpf_cnpj: Mapped[str | None] = mapped_column(String(20))
    arquivo_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("arquivo.id"))
    senha_pfx_cifrada: Mapped[bytes] = mapped_column(LargeBinary)
    numero_serie: Mapped[str | None] = mapped_column(String(80))
    emissor: Mapped[str | None] = mapped_column(String(200))
    validade_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validade_fim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Assinatura(Base):
    __tablename__ = "assinatura"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    documento_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("documento.id"))
    usuario_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("usuario.id"))
    certificado_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("usuario_certificado.id"))
    ordem: Mapped[int] = mapped_column(Integer)
    assinado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    hash_documento: Mapped[str | None] = mapped_column(CHAR(64))
    arquivo_assinado_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("arquivo.id"))
    carimbo_pagina: Mapped[int | None] = mapped_column(Integer)
    carimbo_nova_folha: Mapped[bool] = mapped_column(Boolean, default=False)
    carimbo_posicao: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[AssinaturaStatus] = mapped_column(
        _pg_enum(AssinaturaStatus, "assinatura_status"), default=AssinaturaStatus.valida
    )
    verificado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detalhe_cadeia: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    usuario: Mapped[Usuario] = relationship(lazy="joined")
