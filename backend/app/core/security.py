"""Primitivas de segurança: hash de senha (Argon2id) e tokens JWT.

Substitui o modelo inseguro do legado (senha em texto puro no campo FONE2).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet

from app.core.config import get_settings

_settings = get_settings()
_hasher = PasswordHasher()  # Argon2id com parâmetros padrão da lib
# Chave simétrica para cifragem em repouso (certificados A1 e suas senhas),
# derivada da SECRET_KEY. Em produção, considere uma ENCRYPTION_KEY dedicada.
_fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(_settings.secret_key.encode()).digest()))


# --- Senhas ------------------------------------------------------------------
def hash_senha(senha: str) -> str:
    """Gera o hash Argon2id da senha."""
    return _hasher.hash(senha)


def verificar_senha(senha: str, senha_hash: str) -> bool:
    """Confere a senha contra o hash. Nunca lança para senha errada."""
    try:
        return _hasher.verify(senha_hash, senha)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def precisa_rehash(senha_hash: str) -> bool:
    """Indica se o hash deve ser regravado (parâmetros do Argon2 evoluíram)."""
    return _hasher.check_needs_rehash(senha_hash)


# --- Tokens JWT --------------------------------------------------------------
def _criar_token(subject: str, expira: timedelta, tipo: str, extra: dict[str, Any] | None = None) -> str:
    agora = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": tipo,
        "iat": agora,
        "exp": agora + expira,
        "jti": secrets.token_urlsafe(12),  # torna cada token único (evita colisão no mesmo segundo)
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _settings.secret_key, algorithm=_settings.jwt_algorithm)


def criar_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    return _criar_token(
        subject, timedelta(minutes=_settings.access_token_expire_minutes), "access", extra
    )


def criar_refresh_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    return _criar_token(
        subject, timedelta(days=_settings.refresh_token_expire_days), "refresh", extra
    )


def criar_token_desafio(subject: str) -> str:
    """Token curto que autoriza a 2ª etapa do login (validação do OTP)."""
    return _criar_token(subject, timedelta(minutes=_settings.otp_expire_minutes), "2fa")


def criar_token_reset(subject: str) -> str:
    return _criar_token(subject, timedelta(minutes=30), "reset")


def decodificar_token(token: str) -> dict[str, Any]:
    """Decodifica e valida assinatura/expiração. Lança jwt.PyJWTError se inválido."""
    return jwt.decode(token, _settings.secret_key, algorithms=[_settings.jwt_algorithm])


# --- Códigos OTP / verificação ------------------------------------------------
def gerar_codigo(digitos: int = 6) -> str:
    """Gera um OTP numérico aleatório e imprevisível."""
    return f"{secrets.randbelow(10**digitos):0{digitos}d}"


def hash_codigo(codigo: str) -> str:
    """HMAC-SHA256 do OTP com a SECRET_KEY (rápido; guardamos só o hash)."""
    return hmac.new(_settings.secret_key.encode(), codigo.encode(), hashlib.sha256).hexdigest()


def verificar_codigo(codigo: str, codigo_hash: str) -> bool:
    return hmac.compare_digest(hash_codigo(codigo), codigo_hash)


def hash_refresh(token: str) -> str:
    """Hash do refresh token para guardar na sessão (não guardamos o token em claro)."""
    return hashlib.sha256(token.encode()).hexdigest()


# --- Cifragem em repouso (Fernet/AES) -----------------------------------------
def cifrar(dados: bytes) -> bytes:
    """Cifra bytes para armazenamento em repouso (certificado A1, senha do .pfx)."""
    return _fernet.encrypt(dados)


def decifrar(dados: bytes) -> bytes:
    return _fernet.decrypt(dados)


def sha256_hex(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()
