#!/usr/bin/env bash
# Teste de integração ponta a ponta da autenticação (Fase 1).
# Requer a stack no ar (infra/docker-compose) e um admin já criado (scripts.create_admin).
# Lê os OTPs do log de e-mail de DEV (backend sem SMTP registra o código no log).
#
# Uso:
#   BASE_URL=http://localhost:18080/api/v1 \
#   ADMIN_LOGIN=admin ADMIN_SENHA='Senha@123' GRUPO_ID=1 \
#   bash backend/tests/e2e_auth.sh
set -u
B="${BASE_URL:-http://localhost:18080/api/v1}"
ADMIN_LOGIN="${ADMIN_LOGIN:-admin}"
ADMIN_SENHA="${ADMIN_SENHA:-Senha@123}"
GRUPO_ID="${GRUPO_ID:-1}"
COMPOSE_DIR="${COMPOSE_DIR:-infra}"
CT='Content-Type: application/json'
pass=0; fail=0
jget(){ python3 -c "import sys,json;d=json.load(sys.stdin);print(d$1)" 2>/dev/null; }
codigo(){ (cd "$COMPOSE_DIR" && docker compose logs backend 2>&1) | grep -A3 'DEV-EMAIL' | grep -oE '[0-9]{6}' | tail -1; }
chk(){ if [ "$1" = "$2" ]; then echo "PASS  $3 ($1)"; pass=$((pass+1)); else echo "FAIL  $3 (esperado $2, obtido $1)"; fail=$((fail+1)); fi; }

U="maria_$(date +%s)"; EMAIL="${U}@teste.com.br"

c=$(curl -s -o /dev/null -w '%{http_code}' $B/usuarios/me); chk "$c" 401 "me sem token"
c=$(curl -s -o /dev/null -w '%{http_code}' -X POST $B/usuarios -H "$CT" -d '{"login":"x","email":"x@teste.com.br","grupo_id":1}'); chk "$c" 401 "criar sem admin"

R=$(curl -s -X POST $B/auth/login -H "$CT" -d "{\"login\":\"$ADMIN_LOGIN\",\"senha\":\"$ADMIN_SENHA\"}")
TD=$(echo "$R" | jget "['token_desafio']"); OTP=$(codigo)
R=$(curl -s -X POST $B/auth/2fa -H "$CT" -d "{\"token_desafio\":\"$TD\",\"codigo\":\"$OTP\"}")
ATK=$(echo "$R" | jget "['access_token']")
[ -n "$ATK" ] && { echo "PASS  admin 2FA"; pass=$((pass+1)); } || { echo "FAIL  admin 2FA: $R"; fail=$((fail+1)); }

R=$(curl -s -X POST $B/usuarios -H "$CT" -H "Authorization: Bearer $ATK" -d "{\"login\":\"$U\",\"nome\":\"Maria\",\"email\":\"$EMAIL\",\"grupo_id\":$GRUPO_ID,\"is_admin\":false}")
chk "$(echo "$R" | jget "['status']")" "pendente" "usuario criado pendente"; COTP=$(codigo)

c=$(curl -s -o /dev/null -w '%{http_code}' -X POST $B/auth/confirmar-email -H "$CT" -d "{\"login\":\"$U\",\"codigo\":\"$COTP\",\"nova_senha\":\"MinhaSenha@1\"}"); chk "$c" 204 "confirmar-email"

R=$(curl -s -X POST $B/auth/login -H "$CT" -d "{\"login\":\"$U\",\"senha\":\"MinhaSenha@1\"}"); TD=$(echo "$R" | jget "['token_desafio']"); OTP=$(codigo)
R=$(curl -s -X POST $B/auth/2fa -H "$CT" -d "{\"token_desafio\":\"$TD\",\"codigo\":\"$OTP\"}"); MTK=$(echo "$R" | jget "['access_token']"); MRT=$(echo "$R" | jget "['refresh_token']")
chk "$(curl -s $B/usuarios/me -H "Authorization: Bearer $MTK" | jget "['login']")" "$U" "me = usuario"

R=$(curl -s -X POST $B/auth/refresh -H "$CT" -d "{\"refresh_token\":\"$MRT\"}"); MRT2=$(echo "$R" | jget "['refresh_token']")
[ -n "$MRT2" ] && [ "$MRT2" != "$MRT" ] && { echo "PASS  refresh rotacionado"; pass=$((pass+1)); } || { echo "FAIL  refresh"; fail=$((fail+1)); }
c=$(curl -s -o /dev/null -w '%{http_code}' -X POST $B/auth/refresh -H "$CT" -d "{\"refresh_token\":\"$MRT\"}"); chk "$c" 401 "refresh antigo revogado"
c=$(curl -s -o /dev/null -w '%{http_code}' -X POST $B/auth/logout -H "$CT" -d "{\"refresh_token\":\"$MRT2\"}"); chk "$c" 204 "logout"

curl -s -o /dev/null -X POST $B/auth/esqueci-senha -H "$CT" -d "{\"email\":\"$EMAIL\"}"; ROTP=$(codigo)
c=$(curl -s -o /dev/null -w '%{http_code}' -X POST $B/auth/redefinir-senha -H "$CT" -d "{\"email\":\"$EMAIL\",\"codigo\":\"$ROTP\",\"nova_senha\":\"NovaSenha@2\"}"); chk "$c" 204 "redefinir-senha"

echo ""; echo "==== $pass PASS / $fail FAIL ===="
exit $fail
