#!/usr/bin/env bash
#
# deploy.sh — Atualiza o Digitalizador no SERVIDOR (produção, Bonfim).
#
# Fluxo: desenvolve-se no .82 -> git push -> no servidor roda-se este script,
# que faz git pull + rebuild + restart dos containers, SEM tocar nas imagens.
#
# Uso no servidor:
#     cd <repo>            # a pasta do clone (ex.: ~/digitalizador)
#     ./deploy.sh          # atualiza para o origin/main
#     ./deploy.sh --no-build   # só reinicia (não reconstrói as imagens)
#     ./deploy.sh --status     # só mostra o estado atual (não atualiza)
#
# GARANTIAS DE SEGURANÇA (por que é seguro rodar em produção):
#   * As imagens ficam em bind mounts de host (/data/storage e /data/legado):
#     git pull e docker build NÃO as tocam. Este script NUNCA roda `down`,
#     então o volume do banco (pgdata) também nunca é removido.
#   * `git pull --ff-only`: se o histórico do servidor divergir do GitHub,
#     o script PARA e avisa — nunca faz merge automático às cegas.
#   * Falha cedo se faltar o infra/.env (segredos de produção).
#
set -euo pipefail

# ---- localização (o script descobre a raiz do repo por si) ----
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$REPO/infra"
COMPOSE_FILE="docker-compose.prod.yml"
BRANCH="main"
WEB_PORT_DEFAULT=80

# ---- cores (degradam para texto puro se não for TTY) ----
if [ -t 1 ]; then B=$'\e[1m'; G=$'\e[32m'; Y=$'\e[33m'; R=$'\e[31m'; Z=$'\e[0m'; else B=; G=; Y=; R=; Z=; fi
log()  { echo "${B}==>${Z} $*"; }
ok()   { echo "${G}  OK${Z} $*"; }
warn() { echo "${Y}  ! ${Z} $*"; }
die()  { echo "${R} ERRO:${Z} $*" >&2; exit 1; }

# ---- flags ----
DO_BUILD=1; ONLY_STATUS=0
for arg in "$@"; do
  case "$arg" in
    --no-build) DO_BUILD=0 ;;
    --status)   ONLY_STATUS=1 ;;
    -h|--help)  sed -n '2,25p' "$0"; exit 0 ;;
    *) die "opção desconhecida: $arg (use --help)" ;;
  esac
done

# ---- compose: detecta `docker compose` (v2) ou `docker-compose` (v1) ----
if docker compose version >/dev/null 2>&1; then DC=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then DC=(docker-compose)
else die "docker compose não encontrado no servidor."; fi

cd "$COMPOSE_DIR" || die "pasta infra não encontrada: $COMPOSE_DIR"
dc() { "${DC[@]}" -f "$COMPOSE_FILE" "$@"; }

# WEB_PORT para o smoke test (lido do infra/.env, senão o padrão)
WEB_PORT="$(grep -E '^WEB_PORT=' .env 2>/dev/null | tail -1 | cut -d= -f2)"; WEB_PORT="${WEB_PORT:-$WEB_PORT_DEFAULT}"

estado() {
  log "Containers:"; dc ps || true
  echo
  log "Imagens (NÃO são tocadas pelo deploy):"
  printf '    /data/storage: '; du -sh /data/storage 2>/dev/null || echo "ausente"
  printf '    /data/legado:  '; du -sh /data/legado  2>/dev/null || echo "ausente"
}

if [ "$ONLY_STATUS" = 1 ]; then estado; exit 0; fi

# ---- 0. pré-condições ----
[ -f "$COMPOSE_DIR/.env" ] || die "falta $COMPOSE_DIR/.env — copie de .env.prod.example e preencha os segredos."
command -v git >/dev/null || die "git não instalado no servidor."
git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || die "$REPO não é um clone git. Faça o clone primeiro (veja README/instruções)."

# ---- 1. git: atualizar para origin/main ----
log "Buscando atualizações do GitHub..."
git -C "$REPO" fetch --prune origin
LOCAL="$(git -C "$REPO" rev-parse @)"
REMOTE="$(git -C "$REPO" rev-parse "origin/$BRANCH")"

if [ "$LOCAL" = "$REMOTE" ]; then
  ok "Já está na última versão ($(git -C "$REPO" rev-parse --short @))."
else
  log "Novos commits:"
  git -C "$REPO" --no-pager log --oneline "$LOCAL..$REMOTE" | sed 's/^/    /'
  # alerta se houver mudança local não commitada (não aborta, mas avisa)
  if ! git -C "$REPO" diff --quiet || ! git -C "$REPO" diff --cached --quiet; then
    warn "Há alterações locais não commitadas no servidor — o pull pode falhar."
  fi
  log "Aplicando (fast-forward)..."
  git -C "$REPO" pull --ff-only origin "$BRANCH" \
    || die "pull não-fast-forward: o servidor divergiu do GitHub. Resolva à mão (git status / git log)."
  ok "Agora em $(git -C "$REPO" rev-parse --short @)."
fi

# ---- 2. subir/reconstruir (sem down; recria só o que mudou) ----
if [ "$DO_BUILD" = 1 ]; then
  log "Reconstruindo imagens e subindo containers..."
  dc up --build -d
else
  log "Subindo containers (sem rebuild)..."
  dc up -d
fi

# ---- 3. migrations: o backend roda `alembic upgrade head` ao subir (command do compose) ----
ok "Migrations aplicadas pelo backend no start (alembic upgrade head)."

# ---- 4. smoke test de saúde ----
log "Aguardando a API responder (/api/v1/health/ready)..."
URL="http://localhost:${WEB_PORT}/api/v1/health/ready"
for i in $(seq 1 30); do
  if curl -fsS "$URL" >/dev/null 2>&1; then ok "API saudável: $URL"; break; fi
  [ "$i" = 30 ] && { warn "A API não respondeu em 30 tentativas. Logs:"; dc logs --tail=40 backend || true; die "deploy subiu mas o health falhou."; }
  sleep 2
done

# ---- 5. limpeza de imagens antigas (dangling) ----
log "Removendo imagens órfãs (dangling)..."
docker image prune -f >/dev/null 2>&1 || true

echo
ok "Deploy concluído."
estado
