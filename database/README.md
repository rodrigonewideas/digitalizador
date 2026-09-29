# database/

Modelo de dados PostgreSQL 16 do Digitalizador Bonfim Web.

## Arquivos

| Arquivo | Papel |
|---------|-------|
| `schema.sql` | **Fonte da verdade** do schema (DDL canônico, comentado). |
| `seeds.sql` | Seeds mínimas para bootstrap de DEV (rodar só em banco limpo, antes do ETL). |

O dicionário de dados e o mapeamento com o legado Firebird estão em
[`../docs/02-MODELO-DE-DADOS.md`](../docs/02-MODELO-DE-DADOS.md).

## Como aplicar

O schema é aplicado pela **migration inicial do Alembic** (recomendado):

```bash
cd backend
export DATABASE_URL='postgresql+psycopg://digitalizador:digitalizador@localhost:5432/digitalizador'
alembic upgrade head
```

Ou diretamente com `psql` (útil em dev):

```bash
psql "$DATABASE_URL_PSQL" -f database/schema.sql
psql "$DATABASE_URL_PSQL" -f database/seeds.sql   # opcional, só em dev
```

## Evolução do schema

Enquanto não houver modelos SQLAlchemy, a evolução é feita por **novas migrations
Alembic** (`backend/migrations/versions/000X_*.py`) com SQL explícito. Quando os
modelos forem introduzidos, apontar `target_metadata` em `backend/migrations/env.py`
para habilitar o `--autogenerate`.

> A `schema.sql` continua sendo a referência legível para revisão; mudanças devem
> ser refletidas nela **e** numa migration versionada.
