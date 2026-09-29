"""Guarda de arquivos em sistema de arquivos POSIX (req. 7-8).

Nome físico = UUID (ofuscação), particionado por ano/mês + 2 pares do UUID (sharding).
Registra cada arquivo em `arquivo`; o vínculo com o contrato/documento vive só no banco.
"""
from __future__ import annotations

import uuid as uuidlib
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import get_settings
from app.models import Arquivo, ArquivoPapel, VolumeStorage

_settings = get_settings()

# papel -> atributo de raiz no volume
_RAIZ_ATTR = {
    ArquivoPapel.full: "raiz_full",
    ArquivoPapel.assinado: "raiz_full",
    ArquivoPapel.thumbnail: "raiz_thumb",
    ArquivoPapel.backup: "raiz_backup",
    ArquivoPapel.certificado: "raiz_full",  # sob subpasta _certificados
}


def volume_ativo(db: Session) -> VolumeStorage:
    v = db.scalar(select(VolumeStorage).where(VolumeStorage.ativo).order_by(VolumeStorage.id))
    if v is not None:
        return v
    root = _settings.storage_root
    v = VolumeStorage(
        nome="LOCAL",
        raiz_full=f"{root}/full",
        raiz_thumb=f"{root}/thumb",
        raiz_backup=f"{root}/backup",
        ativo=True,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def _raiz(volume: VolumeStorage, papel: ArquivoPapel) -> Path:
    attr = _RAIZ_ATTR[papel]
    base = getattr(volume, attr) or f"{_settings.storage_root}/{attr.removeprefix('raiz_')}"
    base_path = Path(base)
    if papel == ArquivoPapel.certificado:
        base_path = base_path / "_certificados"
    return base_path


def caminho_de(db: Session, arquivo: Arquivo) -> Path:
    volume = db.get(VolumeStorage, arquivo.volume_id) if arquivo.volume_id else volume_ativo(db)
    return _raiz(volume, arquivo.papel) / arquivo.object_key


def guardar(
    db: Session,
    papel: ArquivoPapel,
    conteudo: bytes,
    *,
    documento_id: int | None = None,
    extensao: str | None = None,
    mime: str | None = None,
    created_by: int | None = None,
    nome_original: str | None = None,
) -> Arquivo:
    volume = volume_ativo(db)
    u = str(uuidlib.uuid4())
    agora = datetime.now(timezone.utc)
    ext = (extensao or "").lstrip(".").lower()
    nome_fisico = f"{u}.{ext}" if ext else u
    object_key = f"{agora:%Y}/{agora:%m}/{u[:2]}/{u[2:4]}/{nome_fisico}"

    destino = _raiz(volume, papel) / object_key
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(conteudo)

    arquivo = Arquivo(
        uuid=u,
        documento_id=documento_id,
        papel=papel,
        volume_id=volume.id,
        object_key=object_key,
        nome_original=security.cifrar(nome_original.encode()) if nome_original else None,
        extensao=ext or None,
        mime=mime,
        tamanho_bytes=len(conteudo),
        checksum_sha256=security.sha256_hex(conteudo),
        created_by=created_by,
    )
    db.add(arquivo)
    db.commit()
    db.refresh(arquivo)
    return arquivo


def ler(db: Session, arquivo: Arquivo) -> bytes:
    return caminho_de(db, arquivo).read_bytes()
