"""Endpoints de usuário: CRUD (admin), dados do logado, correção de e-mail."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import AdminUsuario, CurrentUsuario, SessionDep
from app.models import Grupo, Usuario, UsuarioStatus
from app.schemas.auth import DefinirEmail, RegistrarUsuario, UsuarioOut, UsuarioUpdate
from app.services import auth_service

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get("", response_model=list[UsuarioOut])
def listar(db: SessionDep, _admin: AdminUsuario) -> list[UsuarioOut]:
    usuarios = db.scalars(select(Usuario).order_by(Usuario.login))
    return [UsuarioOut.model_validate(u) for u in usuarios]


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def criar_usuario(dados: RegistrarUsuario, db: SessionDep, _admin: AdminUsuario) -> UsuarioOut:
    """Cria usuário (pendente) e dispara o e-mail de confirmação. Requer admin."""
    return UsuarioOut.model_validate(auth_service.registrar(db, dados))


@router.get("/me", response_model=UsuarioOut)
def me(usuario: CurrentUsuario) -> UsuarioOut:
    return UsuarioOut.model_validate(usuario)


@router.put("/{usuario_id}", response_model=UsuarioOut)
def atualizar(
    usuario_id: int, dados: UsuarioUpdate, db: SessionDep, _admin: AdminUsuario
) -> UsuarioOut:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")
    if dados.grupo_id is not None and db.get(Grupo, dados.grupo_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Grupo inexistente")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(usuario, campo, valor)
    db.commit()
    db.refresh(usuario)
    return UsuarioOut.model_validate(usuario)


@router.post("/{usuario_id}/bloquear", response_model=UsuarioOut)
def bloquear(usuario_id: int, db: SessionDep, admin: AdminUsuario) -> UsuarioOut:
    usuario = _get(db, usuario_id)
    if usuario.id == admin.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Você não pode bloquear a si mesmo.")
    usuario.acesso_cancelado = True
    usuario.status = UsuarioStatus.bloqueado
    db.commit()
    db.refresh(usuario)
    return UsuarioOut.model_validate(usuario)


@router.post("/{usuario_id}/desbloquear", response_model=UsuarioOut)
def desbloquear(usuario_id: int, db: SessionDep, _admin: AdminUsuario) -> UsuarioOut:
    usuario = _get(db, usuario_id)
    usuario.acesso_cancelado = False
    usuario.bloqueado_ate = None
    usuario.tentativas_login = 0
    usuario.status = UsuarioStatus.ativo if usuario.email_verificado else UsuarioStatus.pendente
    db.commit()
    db.refresh(usuario)
    return UsuarioOut.model_validate(usuario)


@router.post("/{usuario_id}/definir-email", response_model=UsuarioOut)
def definir_email(
    usuario_id: int, dados: DefinirEmail, db: SessionDep, _admin: AdminUsuario
) -> UsuarioOut:
    """Admin: corrige o e-mail de um usuário pendente (ex.: migrado) e reenvia a confirmação."""
    return UsuarioOut.model_validate(auth_service.definir_email_pendente(db, usuario_id, dados.email))


def _get(db: SessionDep, usuario_id: int) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")
    return usuario
