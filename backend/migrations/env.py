"""Ambiente de execução do Alembic.

A URL do banco vem da variável de ambiente DATABASE_URL (ex.: definida em infra/.env).
Enquanto os modelos SQLAlchemy não existirem, a migration inicial aplica o DDL
canônico (database/schema.sql). Quando os modelos forem criados, aponte
`target_metadata` para o metadata deles para habilitar o autogenerate.
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# URL de conexão: prioridade para DATABASE_URL; fallback para dev local.
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://digitalizador:digitalizador@localhost:5432/digitalizador",
)
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Sem modelos ainda → autogenerate desligado. Trocar quando houver Base.metadata.
target_metadata = None


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
