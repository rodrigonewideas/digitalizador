#!/usr/bin/env bash
# Integração ponta a ponta da consulta/anexação (Fase a). Requer stack no ar + admin criado.
# Semeia tipos/motivos/registro via psql (idempotente).
#   BASE_URL=http://localhost:18080/api/v1 ADMIN_LOGIN=admin ADMIN_SENHA='Senha@123' \
#   COMPOSE_DIR=infra bash backend/tests/e2e_consulta.sh
set -u
B="${BASE_URL:-http://localhost:18080/api/v1}"
ADMIN_LOGIN="${ADMIN_LOGIN:-admin}"; ADMIN_SENHA="${ADMIN_SENHA:-Senha@123}"
COMPOSE_DIR="${COMPOSE_DIR:-infra}"; CT='Content-Type: application/json'
pass=0; fail=0
dc(){ (cd "$COMPOSE_DIR" && docker compose "$@"); }
jget(){ python3 -c "import sys,json;d=json.load(sys.stdin);print(d$1)" 2>/dev/null; }
codigo(){ dc logs backend 2>&1 | grep -A3 'DEV-EMAIL' | grep -oE '[0-9]{6}' | tail -1; }
chk(){ if [ "$1" = "$2" ]; then echo "PASS  $3 ($1)"; pass=$((pass+1)); else echo "FAIL  $3 (esperado $2, obtido $1)"; fail=$((fail+1)); fi; }

RID=$(( ($(date +%s) % 900000) + 700000 )); LOTE="L$RID"
dc exec -T db psql -U digitalizador -d digitalizador -tAc \
  "INSERT INTO tipo_documento (id,descricao,frente_verso,qtde_folhas,ativo) VALUES (1,'Capa',false,1,true) ON CONFLICT DO NOTHING; \
   INSERT INTO tipo_documento (id,descricao,frente_verso,qtde_folhas,ativo) VALUES (2,'Certidao Obito',false,1,true) ON CONFLICT DO NOTHING; \
   INSERT INTO motivo (id,descricao) VALUES (1,'Ilegivel') ON CONFLICT DO NOTHING; \
   INSERT INTO registro (id,contrato,lote) VALUES ($RID, $RID, '$LOTE');" >/dev/null

R=$(curl -s -X POST $B/auth/login -H "$CT" -d "{\"login\":\"$ADMIN_LOGIN\",\"senha\":\"$ADMIN_SENHA\"}"); TD=$(echo "$R"|jget "['token_desafio']"); OTP=$(codigo)
ATK=$(curl -s -X POST $B/auth/2fa -H "$CT" -d "{\"token_desafio\":\"$TD\",\"codigo\":\"$OTP\"}"|jget "['access_token']")
A="Authorization: Bearer $ATK"

chk "$(curl -s -o /dev/null -w '%{http_code}' "$B/tipos-documento")" "401" "catálogo exige token"
[ "$(curl -s "$B/tipos-documento" -H "$A"|python3 -c 'import sys,json;print(len(json.load(sys.stdin))>=2)')" = "True" ] && { echo "PASS  tipos-documento"; pass=$((pass+1)); } || { echo "FAIL tipos"; fail=$((fail+1)); }
chk "$(curl -s -o /dev/null -w '%{http_code}' "$B/registros" -H "$A")" "422" "busca exige filtro"

R=$(curl -s "$B/registros?lote=$LOTE" -H "$A")
chk "$(echo "$R"|jget "[0]['id']")" "$RID" "busca por lote"
chk "$(echo "$R"|jget "[0]['cessionario']")" "None" "cessionário via gateway (não conectado)"

DID=$(curl -s -X POST "$B/registros/$RID/documentos" -H "$CT" -H "$A" -d '{"tipo_doc_id":2,"nr_folha":1,"total_folhas":1,"face":"F"}'|jget "['id']")
[ -n "$DID" ] && { echo "PASS  documento anexado (id=$DID)"; pass=$((pass+1)); } || { echo "FAIL anexar"; fail=$((fail+1)); }
chk "$(curl -s "$B/registros/$RID/documentos" -H "$A"|jget "[0]['tipo_descricao']")" "Certidao Obito" "documento com tipo"

chk "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$B/documentos/$DID/comentario" -H "$CT" -H "$A" -d '{}')" "422" "comentário vazio -> 422"
chk "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$B/documentos/$DID/comentario" -H "$CT" -H "$A" -d '{"motivo_id":1,"comentario":"ilegivel","refugar":true}')" "201" "comentário + refugar"
chk "$(curl -s "$B/registros/$RID/documentos" -H "$A"|jget "[0]['refugada']")" "True" "documento refugado"
chk "$(curl -s "$B/registros?registro_id=$RID" -H "$A"|jget "[0]['qtde_refugados']")" "1" "refugado contado no registro"

echo ""; echo "==== $pass PASS / $fail FAIL ===="
exit $fail
