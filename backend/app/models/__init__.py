"""Modelos ORM (SQLAlchemy 2).

O schema é criado pelas migrations (database/schema.sql); estes modelos são usados
para consulta/escrita pela aplicação. Ainda não cobrem todas as tabelas — por isso
o Alembic segue com migrations SQL (autogenerate só quando todos os modelos existirem).
"""
from app.models.enums import (
    ArquivoPapel,
    AssinaturaStatus,
    CodigoTipo,
    UsuarioStatus,
)
from app.models.tables import (
    Arquivo,
    Assinatura,
    Caracteristica,
    CodigoVerificacao,
    Documento,
    Grupo,
    IndiceApos1999,
    IndiceOriginal,
    LogAuditoria,
    Motivo,
    Refugo,
    Registro,
    Sessao,
    TipoDocumento,
    Usuario,
    UsuarioCertificado,
    VolumeStorage,
)

__all__ = [
    "ArquivoPapel",
    "AssinaturaStatus",
    "CodigoTipo",
    "UsuarioStatus",
    "Grupo",
    "Usuario",
    "CodigoVerificacao",
    "Sessao",
    "LogAuditoria",
    "VolumeStorage",
    "Arquivo",
    "Documento",
    "Registro",
    "TipoDocumento",
    "Motivo",
    "IndiceOriginal",
    "IndiceApos1999",
    "Caracteristica",
    "Refugo",
    "UsuarioCertificado",
    "Assinatura",
]
