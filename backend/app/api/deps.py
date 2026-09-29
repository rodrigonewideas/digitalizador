"""Dependencies compartilhadas da API."""
from __future__ import annotations

from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.security import decodificar_token
from app.models import Usuario, UsuarioStatus

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=True)

SessionDep = Annotated[Session, Depends(get_session)]


def get_claims(token: Annotated[str, Depends(oauth2_scheme)]) -> dict[str, Any]:
    """Valida o access token e devolve os claims."""
    try:
        claims = decodificar_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if claims.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tipo de token inválido")
    return claims


ClaimsDep = Annotated[dict[str, Any], Depends(get_claims)]


def get_current_usuario(db: SessionDep, claims: ClaimsDep) -> Usuario:
    usuario = db.get(Usuario, int(claims["sub"]))
    if usuario is None or usuario.status != UsuarioStatus.ativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inválido")
    return usuario


CurrentUsuario = Annotated[Usuario, Depends(get_current_usuario)]


def require_admin(usuario: CurrentUsuario) -> Usuario:
    if not usuario.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requer perfil administrador")
    return usuario


AdminUsuario = Annotated[Usuario, Depends(require_admin)]
