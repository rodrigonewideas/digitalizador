"""DTOs de entrada/saída da autenticação."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UsuarioStatus


class RegistrarUsuario(BaseModel):
    login: str = Field(min_length=1, max_length=20)
    nome: str | None = Field(default=None, max_length=100)
    email: EmailStr
    grupo_id: int
    is_admin: bool = False


class ConfirmarCadastro(BaseModel):
    login: str
    codigo: str = Field(min_length=4, max_length=8)
    nova_senha: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    login: str
    senha: str


class DesafioResponse(BaseModel):
    desafio_2fa: bool = True
    token_desafio: str | None = None
    # Preenchidos apenas no modo dev (2FA desativado): login direto.
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    mensagem: str = "Código de verificação enviado para o e-mail cadastrado."


class Verificar2FA(BaseModel):
    token_desafio: str
    codigo: str = Field(min_length=4, max_length=8)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class EsqueciSenha(BaseModel):
    email: EmailStr


class RedefinirSenha(BaseModel):
    email: EmailStr
    codigo: str = Field(min_length=4, max_length=8)
    nova_senha: str = Field(min_length=8, max_length=128)


class DefinirEmail(BaseModel):
    email: EmailStr


class AlterarEmail(BaseModel):
    senha_atual: str
    novo_email: EmailStr


class ConfirmarAlteracaoEmail(BaseModel):
    codigo: str = Field(min_length=4, max_length=8)


class UsuarioOut(BaseModel):
    id: int
    login: str
    nome: str | None
    email: str
    status: UsuarioStatus
    is_admin: bool
    grupo_id: int
    email_verificado: bool
    data_cadastro: date | None = None

    model_config = {"from_attributes": True}


class UsuarioUpdate(BaseModel):
    nome: str | None = Field(default=None, max_length=100)
    grupo_id: int | None = None
    is_admin: bool | None = None
