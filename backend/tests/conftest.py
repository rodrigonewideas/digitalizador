"""Configuração de testes: garante env mínimo antes de importar o app."""
from __future__ import annotations

import os

os.environ.setdefault("SECRET_KEY", "chave-de-teste-nao-usar-em-producao-000000000000")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://digitalizador:test@localhost:5432/digitalizador"
)
os.environ.setdefault("ENVIRONMENT", "test")
