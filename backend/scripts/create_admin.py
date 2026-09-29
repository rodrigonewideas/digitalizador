"""Cria o primeiro usuário administrador (ativo e com e-mail já verificado).

Uso (dentro do backend, com DATABASE_URL/SECRET_KEY no ambiente):
    python -m scripts.create_admin --login admin --email admin@dominio.com.br --senha '****'
Se não passar --senha, é solicitada de forma oculta (getpass).
"""
from __future__ import annotations

import argparse
import getpass

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_senha
from app.models import Grupo, Usuario, UsuarioStatus


def main() -> int:
    ap = argparse.ArgumentParser(description="Cria o primeiro admin")
    ap.add_argument("--login", required=True)
    ap.add_argument("--email", required=True)
    ap.add_argument("--nome", default="Administrador")
    ap.add_argument("--senha", default=None)
    ap.add_argument("--grupo", default="Administradores", help="nome do grupo (criado se não existir)")
    args = ap.parse_args()

    senha = args.senha or getpass.getpass("Senha do admin: ")
    if len(senha) < 8:
        print("Senha deve ter ao menos 8 caracteres.")
        return 2

    with SessionLocal() as db:
        if db.scalar(select(Usuario).where(Usuario.login == args.login)):
            print(f"Login '{args.login}' já existe.")
            return 1
        grupo = db.scalar(select(Grupo).where(Grupo.descricao == args.grupo))
        if grupo is None:
            grupo = Grupo(descricao=args.grupo, ativo=True)
            db.add(grupo)
            db.flush()
        db.add(
            Usuario(
                login=args.login,
                nome=args.nome,
                email=args.email,
                senha_hash=hash_senha(senha),
                email_verificado=True,
                status=UsuarioStatus.ativo,
                is_admin=True,
                grupo_id=grupo.id,
            )
        )
        db.commit()
    print(f"Admin '{args.login}' criado no grupo '{args.grupo}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
