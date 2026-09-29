"""Enums do domínio, espelhando os tipos ENUM do PostgreSQL (database/schema.sql)."""
from __future__ import annotations

from enum import Enum


class UsuarioStatus(str, Enum):
    pendente = "pendente"
    ativo = "ativo"
    bloqueado = "bloqueado"
    desligado = "desligado"


class CodigoTipo(str, Enum):
    cadastro = "cadastro"
    login_2fa = "login_2fa"
    reset_senha = "reset_senha"
    alterar_email = "alterar_email"


class ArquivoPapel(str, Enum):
    full = "full"
    thumbnail = "thumbnail"
    backup = "backup"
    assinado = "assinado"
    certificado = "certificado"


class AssinaturaStatus(str, Enum):
    pendente = "pendente"
    valida = "valida"
    invalida = "invalida"
    revogada = "revogada"
