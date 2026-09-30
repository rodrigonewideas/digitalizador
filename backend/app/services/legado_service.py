"""Localiza no disco as imagens legadas migradas do Windows (Fase 3b).

Os caminhos em `documento_legado` são do sistema antigo — ex.:
``P:\\03162022\\FULL\\426820 25407-092543.jpg`` (P: = share \\\\192.168.5.232\\Imagens).
A cópia (rsync) preservou a estrutura a partir da raiz do share em
``settings.legado_root`` (/data/legado). Aqui o prefixo (letra de drive ou UNC)
é removido e o restante vira caminho POSIX sob essa raiz.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.core.config import get_settings

# "P:\..." ou "\\servidor\share\..."
_PREFIXO = re.compile(r"^(?:[A-Za-z]:|\\\\[^\\]+\\[^\\]+)\\?")

MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".bmp": "image/bmp", ".tif": "image/tiff",
    ".tiff": "image/tiff", ".pdf": "application/pdf",
}


def caminho_local(legacy: str | None) -> Path | None:
    """Converte o caminho legado (Windows) no caminho local sob legado_root."""
    if not legacy:
        return None
    rel = _PREFIXO.sub("", legacy.strip()).replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return None
    return Path(get_settings().legado_root) / rel


def resolver(legacy: str | None) -> Path | None:
    """Arquivo existente no disco, tolerando diferenças de caixa (FAT/NTFS x ext4)."""
    p = caminho_local(legacy)
    if p is None:
        return None
    if p.is_file():
        return p
    for cand in (p.with_suffix(p.suffix.lower()), p.with_suffix(p.suffix.upper())):
        if cand.is_file():
            return cand
    pai = p.parent
    if pai.is_dir():
        alvo = p.name.lower()
        for f in pai.iterdir():
            if f.name.lower() == alvo and f.is_file():
                return f
    return None


def mime_de(p: Path) -> str:
    return MIME.get(p.suffix.lower(), "application/octet-stream")
