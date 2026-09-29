"""initial schema (aplica database/schema.sql)

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-23
"""
import os
from pathlib import Path
from typing import Sequence, Union

from alembic import op

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Local do DDL canônico. No repositório, database/ é irmão de backend/:
#   .../backend/migrations/versions/0001_initial_schema.py
#   parents[0]=versions  parents[1]=migrations  parents[2]=backend  parents[3]=repo raiz
# Em container (WORKDIR /app), defina DIGITALIZADOR_SCHEMA_SQL apontando o schema.sql.
_DEFAULT_SCHEMA = Path(__file__).resolve().parents[3] / "database" / "schema.sql"
SCHEMA_SQL = Path(os.environ.get("DIGITALIZADOR_SCHEMA_SQL", str(_DEFAULT_SCHEMA)))


def upgrade() -> None:
    sql = SCHEMA_SQL.read_text(encoding="utf-8")
    # exec_driver_sql envia o script como comando simples (multi-statement), o que
    # preserva as funções com corpo $$...$$ do schema.sql.
    op.get_bind().exec_driver_sql(sql)


def downgrade() -> None:
    # Migration inicial: recria o schema public do zero.
    op.get_bind().exec_driver_sql("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
