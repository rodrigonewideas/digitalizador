"""Regras de autenticação e gestão de usuário.

Fluxos: cadastro (pendente) -> confirmação de e-mail (define senha, ativa) ->
login em 2 etapas (senha -> OTP por e-mail) -> refresh/logout; reset de senha.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import get_settings
from app.models import CodigoTipo, CodigoVerificacao, Grupo, LogAuditoria, Sessao, Usuario, UsuarioStatus
from app.schemas.auth import ConfirmarCadastro, DesafioResponse, RegistrarUsuario, TokenPair
from app.services.email import enviar_email

_settings = get_settings()
MAX_LOGIN_TENTATIVAS = 5
BLOQUEIO_MINUTOS = 15


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def registrar_log(
    db: Session,
    acao: str,
    usuario_id: int | None = None,
    ip: str | None = None,
    ua: str | None = None,
    detalhe: dict | None = None,
) -> None:
    db.add(LogAuditoria(usuario_id=usuario_id, acao=acao, ip_origem=ip, user_agent=ua, detalhe=detalhe))


# ------------------------------------------------------------------- códigos OTP
def _emitir_codigo(
    db: Session,
    usuario: Usuario,
    tipo: CodigoTipo,
    assunto: str,
    *,
    destino: str | None = None,
    contexto: dict | None = None,
) -> None:
    """Invalida códigos anteriores do mesmo tipo, cria um novo e o envia por e-mail.

    `destino` permite enviar para um endereço diferente do cadastrado (troca de e-mail).
    """
    db.execute(
        update(CodigoVerificacao)
        .where(
            CodigoVerificacao.usuario_id == usuario.id,
            CodigoVerificacao.tipo == tipo,
            CodigoVerificacao.consumido_em.is_(None),
        )
        .values(consumido_em=_agora())
    )
    codigo = security.gerar_codigo()
    db.add(
        CodigoVerificacao(
            usuario_id=usuario.id,
            tipo=tipo,
            codigo_hash=security.hash_codigo(codigo),
            expira_em=_agora() + timedelta(minutes=_settings.otp_expire_minutes),
            contexto=contexto,
        )
    )
    db.commit()
    enviar_email(
        destino or usuario.email,
        assunto,
        f"{assunto}\n\nSeu código é: {codigo}\n"
        f"Válido por {_settings.otp_expire_minutes} minutos.",
    )


def _obter_codigo_valido(
    db: Session, usuario: Usuario, tipo: CodigoTipo, codigo: str
) -> CodigoVerificacao | None:
    """Valida o código (expiração, tentativas, hash) e o consome. Retorna a linha se OK."""
    cod = db.scalar(
        select(CodigoVerificacao)
        .where(
            CodigoVerificacao.usuario_id == usuario.id,
            CodigoVerificacao.tipo == tipo,
            CodigoVerificacao.consumido_em.is_(None),
        )
        .order_by(CodigoVerificacao.created_at.desc())
        .limit(1)
    )
    if cod is None or cod.expira_em < _agora():
        return None
    cod.tentativas += 1
    if cod.tentativas > _settings.otp_max_tentativas:
        cod.consumido_em = _agora()
        db.commit()
        return None
    if not security.verificar_codigo(codigo, cod.codigo_hash):
        db.commit()
        return None
    cod.consumido_em = _agora()
    db.commit()
    return cod


def _validar_codigo(db: Session, usuario: Usuario, tipo: CodigoTipo, codigo: str) -> bool:
    return _obter_codigo_valido(db, usuario, tipo, codigo) is not None


def _email_em_uso(db: Session, email: str, exceto_id: int) -> bool:
    outro = db.scalar(select(Usuario).where(Usuario.email == email))
    return outro is not None and outro.id != exceto_id


# --------------------------------------------------------------------- cadastro
def registrar(db: Session, dados: RegistrarUsuario) -> Usuario:
    if db.get(Grupo, dados.grupo_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Grupo inexistente")
    if db.scalar(select(Usuario).where(Usuario.login == dados.login)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Login já cadastrado")
    if db.scalar(select(Usuario).where(Usuario.email == dados.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "E-mail já cadastrado")

    usuario = Usuario(
        login=dados.login,
        nome=dados.nome,
        email=dados.email,
        grupo_id=dados.grupo_id,
        is_admin=dados.is_admin,
        status=UsuarioStatus.pendente,
        email_verificado=False,
        senha_hash=None,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    _emitir_codigo(db, usuario, CodigoTipo.cadastro, "Confirmação de cadastro - Digitalizador Bonfim")
    registrar_log(db, "usuario_criado", usuario_id=usuario.id)
    db.commit()
    return usuario


def confirmar_cadastro(db: Session, dados: ConfirmarCadastro) -> None:
    usuario = db.scalar(select(Usuario).where(Usuario.login == dados.login))
    if usuario is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Código inválido")
    if not _validar_codigo(db, usuario, CodigoTipo.cadastro, dados.codigo):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Código inválido ou expirado")
    usuario.senha_hash = security.hash_senha(dados.nova_senha)
    usuario.email_verificado = True
    usuario.status = UsuarioStatus.ativo
    registrar_log(db, "cadastro_confirmado", usuario_id=usuario.id)
    db.commit()


# ------------------------------------------------------------------------ login
def autenticar(
    db: Session, login: str, senha: str, ip: str | None = None, ua: str | None = None
) -> DesafioResponse:
    """1ª etapa: valida senha e dispara o OTP. Retorna o token de desafio (2FA).

    Em modo dev (dev_2fa_bypass=true e environment != prod), pula o OTP e já
    devolve os tokens de acesso — para agilizar testes de tela.
    """
    generico = HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário ou senha inválidos")
    usuario = db.scalar(select(Usuario).where(Usuario.login == login))
    if usuario is None or usuario.senha_hash is None:
        raise generico
    if usuario.acesso_cancelado or usuario.status in (UsuarioStatus.bloqueado, UsuarioStatus.desligado):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso bloqueado. Procure o administrador.")
    if usuario.bloqueado_ate and usuario.bloqueado_ate > _agora():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Muitas tentativas. Tente mais tarde.")
    if usuario.status != UsuarioStatus.ativo or not usuario.email_verificado:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cadastro pendente de confirmação de e-mail.")

    if not security.verificar_senha(senha, usuario.senha_hash):
        usuario.tentativas_login += 1
        if usuario.tentativas_login >= MAX_LOGIN_TENTATIVAS:
            usuario.status = UsuarioStatus.bloqueado
            usuario.bloqueado_ate = _agora() + timedelta(minutes=BLOQUEIO_MINUTOS)
        registrar_log(db, "login_falha", usuario_id=usuario.id, ip=ip)
        db.commit()
        raise generico

    usuario.tentativas_login = 0
    db.commit()

    # Modo dev: pula o 2FA e loga direto (nunca em produção).
    if _settings.dev_2fa_bypass and not _settings.is_prod:
        par = _emitir_par(db, usuario, ip, ua)
        usuario.ultimo_login = _agora()
        registrar_log(db, "login_sem_2fa_dev", usuario_id=usuario.id, ip=ip)
        db.commit()
        return DesafioResponse(
            desafio_2fa=False,
            access_token=par.access_token,
            refresh_token=par.refresh_token,
            mensagem="Login direto (2FA desativado em modo de teste).",
        )

    _emitir_codigo(db, usuario, CodigoTipo.login_2fa, "Código de acesso - Digitalizador Bonfim")
    registrar_log(db, "login_senha_ok", usuario_id=usuario.id, ip=ip)
    db.commit()
    return DesafioResponse(desafio_2fa=True, token_desafio=security.criar_token_desafio(str(usuario.id)))


def _emitir_par(db: Session, usuario: Usuario, ip: str | None, ua: str | None) -> TokenPair:
    access = security.criar_access_token(str(usuario.id), {"adm": usuario.is_admin})
    refresh = security.criar_refresh_token(str(usuario.id))
    db.add(
        Sessao(
            usuario_id=usuario.id,
            refresh_token_hash=security.hash_refresh(refresh),
            expira_em=_agora() + timedelta(days=_settings.refresh_token_expire_days),
            ip_origem=ip,
            user_agent=ua,
        )
    )
    return TokenPair(access_token=access, refresh_token=refresh)


def verificar_2fa(
    db: Session, token_desafio: str, codigo: str, ip: str | None = None, ua: str | None = None
) -> TokenPair:
    """2ª etapa: valida o OTP e emite os tokens."""
    try:
        claims = security.decodificar_token(token_desafio)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Desafio inválido ou expirado") from exc
    if claims.get("type") != "2fa":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token de desafio inválido")
    usuario = db.get(Usuario, int(claims["sub"]))
    if usuario is None or usuario.status != UsuarioStatus.ativo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário inválido")
    if not _validar_codigo(db, usuario, CodigoTipo.login_2fa, codigo):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Código inválido ou expirado")

    par = _emitir_par(db, usuario, ip, ua)
    usuario.ultimo_login = _agora()
    registrar_log(db, "login_2fa_ok", usuario_id=usuario.id, ip=ip)
    db.commit()
    return par


def refresh(db: Session, refresh_token: str, ip: str | None = None, ua: str | None = None) -> TokenPair:
    try:
        claims = security.decodificar_token(refresh_token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh inválido") from exc
    if claims.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")
    sessao = db.scalar(
        select(Sessao).where(Sessao.refresh_token_hash == security.hash_refresh(refresh_token))
    )
    if sessao is None or sessao.revogado_em is not None or sessao.expira_em < _agora():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão expirada ou revogada")
    usuario = db.get(Usuario, int(claims["sub"]))
    if usuario is None or usuario.status != UsuarioStatus.ativo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário inválido")

    sessao.revogado_em = _agora()  # rotação: revoga o antigo
    par = _emitir_par(db, usuario, ip, ua)
    db.commit()
    return par


def logout(db: Session, refresh_token: str) -> None:
    sessao = db.scalar(
        select(Sessao).where(Sessao.refresh_token_hash == security.hash_refresh(refresh_token))
    )
    if sessao and sessao.revogado_em is None:
        sessao.revogado_em = _agora()
        registrar_log(db, "logout", usuario_id=sessao.usuario_id)
        db.commit()


# ------------------------------------------------------------------ reset senha
def solicitar_reset(db: Session, email: str) -> None:
    usuario = db.scalar(select(Usuario).where(Usuario.email == email))
    # Resposta sempre igual (não revela se o e-mail existe).
    if usuario and usuario.status not in (UsuarioStatus.desligado,):
        _emitir_codigo(db, usuario, CodigoTipo.reset_senha, "Redefinição de senha - Digitalizador Bonfim")


def redefinir_senha(db: Session, email: str, codigo: str, nova_senha: str) -> None:
    usuario = db.scalar(select(Usuario).where(Usuario.email == email))
    if usuario is None or not _validar_codigo(db, usuario, CodigoTipo.reset_senha, codigo):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Código inválido ou expirado")
    usuario.senha_hash = security.hash_senha(nova_senha)
    if usuario.status == UsuarioStatus.bloqueado:
        usuario.status = UsuarioStatus.ativo
    usuario.bloqueado_ate = None
    usuario.tentativas_login = 0
    # Revoga todas as sessões ativas por segurança.
    db.execute(
        update(Sessao)
        .where(Sessao.usuario_id == usuario.id, Sessao.revogado_em.is_(None))
        .values(revogado_em=_agora())
    )
    registrar_log(db, "senha_redefinida", usuario_id=usuario.id)
    db.commit()


# ------------------------------------------------------------------ troca de e-mail
def definir_email_pendente(db: Session, usuario_id: int, novo_email: str) -> Usuario:
    """Admin: corrige/define o e-mail de um usuário PENDENTE (ex.: migrado com placeholder)
    e reenvia o código de confirmação de cadastro para o novo endereço."""
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")
    if usuario.status != UsuarioStatus.pendente:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Usuário já ativo. A troca de e-mail é feita pelo próprio usuário.",
        )
    if _email_em_uso(db, novo_email, usuario.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "E-mail já cadastrado")

    usuario.email = novo_email
    usuario.email_verificado = False
    db.commit()
    _emitir_codigo(
        db, usuario, CodigoTipo.cadastro,
        "Confirmação de cadastro - Digitalizador Bonfim", destino=novo_email,
    )
    registrar_log(db, "email_definido_admin", usuario_id=usuario.id)
    db.commit()
    return usuario


def alterar_email(db: Session, usuario: Usuario, senha_atual: str, novo_email: str) -> None:
    """Usuário ativo: solicita troca do próprio e-mail; envia código ao NOVO endereço."""
    if usuario.senha_hash is None or not security.verificar_senha(senha_atual, usuario.senha_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Senha atual inválida")
    if _email_em_uso(db, novo_email, usuario.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "E-mail já cadastrado")
    _emitir_codigo(
        db, usuario, CodigoTipo.alterar_email,
        "Confirmação de troca de e-mail - Digitalizador Bonfim",
        destino=novo_email, contexto={"novo_email": novo_email},
    )
    registrar_log(db, "alterar_email_solicitado", usuario_id=usuario.id)
    db.commit()


def confirmar_alteracao_email(db: Session, usuario: Usuario, codigo: str) -> None:
    cod = _obter_codigo_valido(db, usuario, CodigoTipo.alterar_email, codigo)
    if cod is None or not cod.contexto or "novo_email" not in cod.contexto:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Código inválido ou expirado")
    novo_email = cod.contexto["novo_email"]
    if _email_em_uso(db, novo_email, usuario.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "E-mail já cadastrado")
    usuario.email = novo_email
    usuario.email_verificado = True
    registrar_log(db, "email_alterado", usuario_id=usuario.id)
    db.commit()
