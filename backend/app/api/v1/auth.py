"""Endpoints de autenticação (login 2 etapas, confirmação, refresh, reset)."""
from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.api.deps import CurrentUsuario, SessionDep
from app.schemas.auth import (
    AlterarEmail,
    ConfirmarAlteracaoEmail,
    ConfirmarCadastro,
    DesafioResponse,
    EsqueciSenha,
    LoginRequest,
    LogoutRequest,
    RedefinirSenha,
    RefreshRequest,
    TokenPair,
    Verificar2FA,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _ip(req: Request) -> str | None:
    return req.client.host if req.client else None


@router.post("/login", response_model=DesafioResponse)
def login(dados: LoginRequest, db: SessionDep, req: Request) -> DesafioResponse:
    """1ª etapa: valida a senha e envia o código de 2FA (ou loga direto no modo dev)."""
    return auth_service.autenticar(
        db, dados.login, dados.senha, ip=_ip(req), ua=req.headers.get("user-agent")
    )


@router.post("/2fa", response_model=TokenPair)
def verificar_2fa(dados: Verificar2FA, db: SessionDep, req: Request) -> TokenPair:
    """2ª etapa: valida o código e emite os tokens."""
    return auth_service.verificar_2fa(
        db, dados.token_desafio, dados.codigo, ip=_ip(req), ua=req.headers.get("user-agent")
    )


@router.post("/confirmar-email", status_code=status.HTTP_204_NO_CONTENT)
def confirmar_email(dados: ConfirmarCadastro, db: SessionDep) -> None:
    """Confirma o cadastro (define a senha e ativa o usuário)."""
    auth_service.confirmar_cadastro(db, dados)


@router.post("/refresh", response_model=TokenPair)
def refresh(dados: RefreshRequest, db: SessionDep, req: Request) -> TokenPair:
    return auth_service.refresh(db, dados.refresh_token, ip=_ip(req), ua=req.headers.get("user-agent"))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(dados: LogoutRequest, db: SessionDep) -> None:
    auth_service.logout(db, dados.refresh_token)


@router.post("/esqueci-senha", status_code=status.HTTP_202_ACCEPTED)
def esqueci_senha(dados: EsqueciSenha, db: SessionDep) -> dict[str, str]:
    auth_service.solicitar_reset(db, dados.email)
    return {"mensagem": "Se o e-mail existir, enviaremos um código de redefinição."}


@router.post("/redefinir-senha", status_code=status.HTTP_204_NO_CONTENT)
def redefinir_senha(dados: RedefinirSenha, db: SessionDep) -> None:
    auth_service.redefinir_senha(db, dados.email, dados.codigo, dados.nova_senha)


@router.post("/alterar-email", status_code=status.HTTP_202_ACCEPTED)
def alterar_email(dados: AlterarEmail, db: SessionDep, usuario: CurrentUsuario) -> dict[str, str]:
    """Solicita troca do próprio e-mail; envia código de confirmação ao novo endereço."""
    auth_service.alterar_email(db, usuario, dados.senha_atual, dados.novo_email)
    return {"mensagem": "Enviamos um código para o novo e-mail. Confirme para concluir a troca."}


@router.post("/confirmar-alteracao-email", status_code=status.HTTP_204_NO_CONTENT)
def confirmar_alteracao_email(
    dados: ConfirmarAlteracaoEmail, db: SessionDep, usuario: CurrentUsuario
) -> None:
    auth_service.confirmar_alteracao_email(db, usuario, dados.codigo)
