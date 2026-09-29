"""Testes das primitivas de segurança (não precisam de banco)."""
from __future__ import annotations

import jwt
import pytest

from app.core import security


def test_hash_e_verifica_senha() -> None:
    h = security.hash_senha("MinhaSenha@1")
    assert h != "MinhaSenha@1"
    assert security.verificar_senha("MinhaSenha@1", h)
    assert not security.verificar_senha("errada", h)


def test_verificar_senha_nao_lanca_para_hash_invalido() -> None:
    assert security.verificar_senha("x", "nao-e-um-hash") is False


def test_access_token_roundtrip() -> None:
    tok = security.criar_access_token("42", {"adm": True})
    claims = security.decodificar_token(tok)
    assert claims["sub"] == "42"
    assert claims["type"] == "access"
    assert claims["adm"] is True


def test_tipos_de_token() -> None:
    assert security.decodificar_token(security.criar_refresh_token("1"))["type"] == "refresh"
    assert security.decodificar_token(security.criar_token_desafio("1"))["type"] == "2fa"
    assert security.decodificar_token(security.criar_token_reset("1"))["type"] == "reset"


def test_tokens_sao_unicos_no_mesmo_segundo() -> None:
    # regressão: dois refresh no mesmo segundo não podem colidir (jti aleatório)
    a = security.criar_refresh_token("1")
    b = security.criar_refresh_token("1")
    assert a != b
    assert security.hash_refresh(a) != security.hash_refresh(b)


def test_token_invalido_lanca() -> None:
    with pytest.raises(jwt.PyJWTError):
        security.decodificar_token("token.invalido.aqui")


def test_codigo_otp_formato_e_hash() -> None:
    codigo = security.gerar_codigo()
    assert len(codigo) == 6 and codigo.isdigit()
    h = security.hash_codigo(codigo)
    assert security.verificar_codigo(codigo, h)
    assert not security.verificar_codigo("000000", h) or codigo == "000000"
