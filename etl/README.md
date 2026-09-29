# etl/

Migração dos **metadados** do sistema legado (dump Firebird `digitalizador_dados`) para o
PostgreSQL do sistema novo. **Não** copia os binários das imagens — isso é a fase 3b, feita quando
os HDs forem disponibilizados (ver `docs/01 §4`). Aqui os caminhos legados são preservados em
`documento_legado` para essa cópia futura.

## Módulos

| Arquivo | Papel |
|---------|-------|
| `fb_parser.py` | Lê o dump SQL do Firebird → `(TABELA, {coluna: valor})`. Trata `''`, NULL, datas, latin-1. |
| `casts.py` | Conversões: trim de CHAR, `S/N`→bool, datas, int/float. |
| `migrate.py` | Migrator: buckets `.jsonl`, carga em ordem de FK, nulificação de órfãos, reset de sequences. |
| `run.py` | CLI + relatório de conciliação. |
| `tests/` | Testes do parser. |

## Como rodar

Pré-requisito: o schema já aplicado no PostgreSQL de destino (via Alembic).

```bash
# a partir da raiz do repositório, com psycopg instalado
export DATABASE_URL='postgresql://digitalizador:senha@localhost:5432/digitalizador'

# carga completa (~500k documentos)
python -m etl.run --dump /caminho/para/digitalizador_dados

# teste rápido (limita a 5.000 imagens)
python -m etl.run --dump /caminho/para/digitalizador_dados --max-images 5000
```

Rodando dentro da rede do Compose (host do banco = `db`):

```bash
docker run --rm --network digitalizador_default -w /repo \
  -v "$PWD":/repo -v /caminho/digitalizador_dados:/data/dump:ro \
  -e DATABASE_URL=postgresql://digitalizador:SENHA@db:5432/digitalizador \
  python:3.12-slim bash -lc "pip install -q 'psycopg[binary]' && python -m etl.run --dump /data/dump"
```

## Regras de transformação

- IDs legados **preservados**; sequences `IDENTITY` reajustadas ao final.
- `CHAR` sofre trim; `'S'/'N'`→`BOOLEAN`; datas→`timestamptz`/`date`.
- **Senhas não migram** (o legado guardava em texto puro em `FONE2`): todos os usuários entram como
  `status='pendente'`, `senha_hash=NULL` → reset + confirmação de e-mail. `FONE2` é descartado;
  `fone_principal←FONE1`, `fone_secundario←FONE0`.
- E-mails ausentes/duplicados recebem placeholder `user<id>@migrado.invalid`.
- FKs órfãs viram `NULL` (contabilizadas); `documento` sem `registro` válido é **pulado** (idem
  linhas com pai obrigatório ausente). Tudo aparece no relatório de conciliação.
- `SEQ_IMAGEM` e `TEMP` são descartadas.

## Testes

```bash
python -m etl.tests.test_fb_parser   # ou: pytest etl/tests
```
