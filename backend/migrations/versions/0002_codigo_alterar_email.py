"""codigo_tipo 'alterar_email' + codigo_verificacao.contexto

Fresh installs já recebem isto pelo schema.sql (0001); esta migration atualiza
bancos já migrados. Ambos os comandos são idempotentes.

Revision ID: 0002_codigo_alterar_email
Revises: 0001_initial_schema
Create Date: 2026-09-24
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_codigo_alterar_email"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.get_bind().exec_driver_sql(
        "ALTER TYPE codigo_tipo ADD VALUE IF NOT EXISTS 'alterar_email'"
    )
    op.get_bind().exec_driver_sql(
        "ALTER TABLE codigo_verificacao ADD COLUMN IF NOT EXISTS contexto JSONB"
    )


def downgrade() -> None:
    # PostgreSQL não remove valores de ENUM; removemos apenas a coluna.
    op.get_bind().exec_driver_sql("ALTER TABLE codigo_verificacao DROP COLUMN IF EXISTS contexto")
