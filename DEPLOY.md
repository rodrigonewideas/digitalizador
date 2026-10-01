# Deploy — Digitalizador Bonfim

Fluxo de trabalho: **desenvolve-se no .82 → `git push` → atualiza-se no servidor com `git pull` + rebuild**.
O servidor oficial roda em `192.168.5.20` (Docker Compose + Nginx).

> GitHub (fonte única da verdade): `https://github.com/rodrigonewideas/digitalizador.git`

---

## 1. No .82 (desenvolvimento) — enviar alterações

```bash
cd /home/rps/digitalizador
git add -A
git commit -m "descrição da mudança"
git push
```

## 2. No servidor (192.168.5.20) — atualizar e testar

A atualização é um comando só: o `deploy.sh` faz `git pull` + rebuild + restart,
**sem tocar nas imagens** (`/data/storage` e `/data/legado` são bind mounts de host)
e **sem apagar o banco** (nunca roda `down`; o volume `pgdata` é preservado).

```bash
ssh USUARIO@192.168.5.20 'cd CAMINHO_DO_REPO && ./deploy.sh'
```

> ⚠️ Substitua `USUARIO` e `CAMINHO_DO_REPO` pelos valores reais do servidor
> (confirmados pelo diagnóstico — ver seção 4).

Variações:

```bash
./deploy.sh              # atualiza para origin/main (pull + rebuild + restart + smoke test)
./deploy.sh --no-build   # só reinicia os containers (sem reconstruir)
./deploy.sh --status     # só mostra o estado atual (containers + tamanho das imagens)
```

---

## 3. Primeira vez no servidor (se ainda não for um clone git)

Se o código no servidor **não** veio de um `git clone` deste repositório, faça o clone
uma vez, preserve os segredos e o `.env` de produção:

```bash
# como o usuário de deploy, numa pasta de sua escolha (ex.: ~/)
git clone https://github.com/rodrigonewideas/digitalizador.git
cd digitalizador

# segredos de produção (NÃO vão no git):
cp infra/.env.prod.example infra/.env
nano infra/.env          # preencher SECRET_KEY, POSTGRES_PASSWORD (= DATABASE_URL),
                         # PDV_FB_* (Firebird), SMTP_* quando houver, etc.

./deploy.sh
```

Gerar segredos fortes:
```bash
openssl rand -hex 32   # SECRET_KEY
openssl rand -hex 16   # POSTGRES_PASSWORD (use o MESMO valor na DATABASE_URL)
```

---

## 4. O que o `deploy.sh` garante

| Risco | Proteção |
|---|---|
| Perder as imagens digitalizadas | `/data/storage` e `/data/legado` são bind mounts de host — build/pull não os tocam |
| Perder o banco | O script **nunca** roda `down`; o volume `pgdata` permanece |
| Merge às cegas | `git pull --ff-only` — se o servidor divergir do GitHub, **para e avisa** |
| Subir sem segredos | Falha cedo se faltar `infra/.env` |
| Subir quebrado sem perceber | Smoke test em `/api/v1/health/ready` após o start |
| Lixo de imagens antigas | `docker image prune -f` ao final (só dangling) |

Migrations do banco são aplicadas automaticamente pelo backend ao subir
(`alembic upgrade head`, no `command` do `docker-compose.prod.yml`).
