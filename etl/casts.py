"""Conversões de valor legado (Firebird) -> tipos do PostgreSQL."""
from __future__ import annotations

from datetime import datetime
from typing import Any


def txt(v: Any) -> str | None:
    """Trim de CHAR/VARCHAR; string vazia vira None."""
    if v is None:
        return None
    s = str(v).rstrip()
    return s or None


def txt_req(v: Any, fallback: str = "") -> str:
    """Como txt, mas nunca None (para colunas NOT NULL)."""
    return txt(v) or fallback


def sn_bool(v: Any, default: bool | None = None) -> bool | None:
    """'S' -> True, 'N' -> False, resto -> default."""
    if v is None:
        return default
    s = str(v).strip().upper()
    if s == "S":
        return True
    if s == "N":
        return False
    return default


def to_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None


def to_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def to_dt(v: Any) -> datetime | None:
    """Parseia 'YYYY-MM-DD HH:MM:SS' ou 'YYYY-MM-DD'. Inválido -> None."""
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
    return None
