# Imagem do backend. Build context = RAIZ do repositório (ver infra/docker-compose.yml),
# para copiar backend/ e database/ (schema.sql aplicado pela migration inicial).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DIGITALIZADOR_SCHEMA_SQL=/app/database/schema.sql

WORKDIR /app

# Usuário sem privilégios (não rodar como root)
RUN groupadd --system app && useradd --system --gid app --home /app app

# Dependências (camada cacheável)
COPY backend/pyproject.toml backend/README.md ./
COPY backend/app ./app
RUN pip install .

# Código de migrations + DDL canônico
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/scripts ./scripts
COPY database ./database

RUN mkdir -p /data/storage && chown -R app:app /app /data/storage
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
