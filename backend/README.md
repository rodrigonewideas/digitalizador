# backend/

API do Digitalizador Bonfim Web — **FastAPI + SQLAlchemy 2 + Alembic** (Python 3.12).

## Estrutura

```
app/
  main.py            # app factory (create_app)
  core/
    config.py        # Settings tipadas (lê env; segredos sem default)
    database.py      # engine/sessão SQLAlchemy + Base
    security.py      # Argon2id (senha) + JWT
  api/
    deps.py          # dependencies (sessão, claims do token)
    v1/
      router.py      # agrega os routers da v1
      health.py      # /health/live e /health/ready
migrations/          # Alembic (0001 aplica database/schema.sql)
alembic.ini
pyproject.toml       # deps + padrão de código (ruff/mypy/pytest)
```

## Rodar em desenvolvimento (Docker)

Pela raiz do repo, via Compose (sobe Postgres, roda migrations e a API):

```bash
cd infra
cp .env.example .env      # ajuste SECRET_KEY e senhas
docker compose up --build
# API:  http://localhost:8000/docs
# Saúde: http://localhost:8000/api/v1/health/ready
```

## Rodar localmente (sem Docker)

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL='postgresql+psycopg://digitalizador:senha@localhost:5432/digitalizador'
export SECRET_KEY="$(openssl rand -hex 32)"
alembic upgrade head
uvicorn app.main:app --reload
```

## Primeiro admin

```bash
docker compose exec backend python -m scripts.create_admin \
  --login admin --email admin@dominio.com.br --nome "Administrador"
```

## Autenticação

Fluxo (login 2 etapas, confirmação de e-mail, 2FA, reset) documentado em
[../docs/04-AUTENTICACAO.md](../docs/04-AUTENTICACAO.md).

## Qualidade

```bash
ruff check . && ruff format --check .
mypy app
pytest                       # unitários (tests/test_security.py)
bash tests/e2e_auth.sh       # integração ponta a ponta (stack no ar + admin criado)
```

Convenções em [../docs/03-PADROES-DE-DESENVOLVIMENTO.md](../docs/03-PADROES-DE-DESENVOLVIMENTO.md).
