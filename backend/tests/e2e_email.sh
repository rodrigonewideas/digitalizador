#!/usr/bin/env bash
# Integração ponta a ponta do fluxo de e-mail (Fase 1c):
#   - admin corrige e-mail de usuário pendente e reenvia confirmação (destrava migrados);
#   - usuário confirma (define senha, ativa) e loga;
#   - troca de e-mail self-service (código ao novo endereço).
# Requer a stack no ar e um admin criado. Lê OTPs do log de e-mail de DEV.
#   BASE_URL=http://localhost:18080/api/v1 ADMIN_LOGIN=admin ADMIN_SENHA='Senha@123' GRUPO_ID=1 \
#   bash backend/tests/e2e_email.sh
set -u
B="${BASE_URL:-http://localhost:18080/api/v1}"
ADMIN_LOGIN="${ADMIN_LOGIN:-admin}"; ADMIN_SENHA="${ADMIN_SENHA:-Senha@123}"; GRUPO_ID="${GRUPO_ID:-1}"
COMPOSE_DIR="${COMPOSE_DIR:-infra}"; CT='Content-Type: application/json'
pass=0; fail=0
jget(){ python3 -c "import sys,json;d=json.load(sys.stdin);print(d$1)" 2>/dev/null; }
codigo(){ (cd "$COMPOSE_DIR" && docker compose logs backend 2>&1) | grep -A3 'DEV-EMAIL' | grep -oE '[0-9]{6}' | tail -1; }
chk(){ if [ "$1" = "$2" ]; then echo "PASS  $3 ($1)"; pass=$((pass+1)); else echo "FAIL  $3 (esperado $2, obtido $1)"; fail=$((fail+1)); fi; }

TS=$(date +%s); U="legado_$TS"; E1="${U}@teste.com.br"; E2="${U}b@teste.com.br"

# admin autentica
R=$(curl -s -X POST $B/auth/login -H "$CT" -d "{\"login\":\"$ADMIN_LOGIN\",\"senha\":\"$ADMIN_SENHA\"}"); TD=$(echo "$R"|jget "['token_desafio']"); OTP=$(codigo)
ATK=$(curl -s -X POST $B/auth/2fa -H "$CT" -d "{\"token_desafio\":\"$TD\",\"codigo\":\"$OTP\"}" | jget "['access_token']")

# admin cria usuario (pendente) e depois CORRIGE o e-mail (definir-email)
R=$(curl -s -X POST $B/usuarios -H "$CT" -H "Authorization: Bearer $ATK" -d "{\"login\":\"$U\",\"email\":\"errado_$E1\",\"grupo_id\":$GRUPO_ID}")
NUID=$(echo "$R"|jget "['id']")
R=$(curl -s -X POST $B/usuarios/$NUID/definir-email -H "$CT" -H "Authorization: Bearer $ATK" -d "{\"email\":\"$E1\"}")
chk "$(echo "$R"|jget "['email']")" "$E1" "admin corrigiu e-mail"; COTP=$(codigo)

c=$(curl -s -o /dev/null -w '%{http_code}' -X POST $B/auth/confirmar-email -H "$CT" -d "{\"login\":\"$U\",\"codigo\":\"$COTP\",\"nova_senha\":\"Legado@123\"}"); chk "$c" 204 "confirmar-email"

R=$(curl -s -X POST $B/auth/login -H "$CT" -d "{\"login\":\"$U\",\"senha\":\"Legado@123\"}"); TD=$(echo "$R"|jget "['token_desafio']"); OTP=$(codigo)
LTK=$(curl -s -X POST $B/auth/2fa -H "$CT" -d "{\"token_desafio\":\"$TD\",\"codigo\":\"$OTP\"}" | jget "['access_token']")
chk "$(curl -s $B/usuarios/me -H "Authorization: Bearer $LTK"|jget "['email']")" "$E1" "login destravado + email"

c=$(curl -s -o /dev/null -w '%{http_code}' -X POST $B/auth/alterar-email -H "$CT" -H "Authorization: Bearer $LTK" -d "{\"senha_atual\":\"Legado@123\",\"novo_email\":\"$E2\"}"); chk "$c" 202 "solicitar troca"
ETP=$(codigo)
c=$(curl -s -o /dev/null -w '%{http_code}' -X POST $B/auth/confirmar-alteracao-email -H "$CT" -H "Authorization: Bearer $LTK" -d "{\"codigo\":\"$ETP\"}"); chk "$c" 204 "confirmar troca"
chk "$(curl -s $B/usuarios/me -H "Authorization: Bearer $LTK"|jget "['email']")" "$E2" "email trocado"

c=$(curl -s -o /dev/null -w '%{http_code}' -X POST $B/usuarios/$NUID/definir-email -H "$CT" -H "Authorization: Bearer $ATK" -d '{"email":"x@teste.com.br"}'); chk "$c" 409 "definir-email em ativo -> 409"
c=$(curl -s -o /dev/null -w '%{http_code}' -X POST $B/auth/alterar-email -H "$CT" -H "Authorization: Bearer $LTK" -d '{"senha_atual":"errada","novo_email":"z@teste.com.br"}'); chk "$c" 401 "alterar-email senha errada -> 401"

echo ""; echo "==== $pass PASS / $fail FAIL ===="
exit $fail
