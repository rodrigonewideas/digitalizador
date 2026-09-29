#!/usr/bin/env bash
# Integração ponta a ponta da assinatura A1 (req. 4-6). Requer stack no ar + admin criado.
# Gera as fixtures (.pfx autoassinado + PDF com rodapé ocupado) dentro do container.
#   BASE_URL=http://localhost:18080/api/v1 ADMIN_LOGIN=admin ADMIN_SENHA='Senha@123' \
#   COMPOSE_DIR=infra bash backend/tests/e2e_assinatura.sh
set -u
B="${BASE_URL:-http://localhost:18080/api/v1}"
ADMIN_LOGIN="${ADMIN_LOGIN:-admin}"; ADMIN_SENHA="${ADMIN_SENHA:-Senha@123}"
COMPOSE_DIR="${COMPOSE_DIR:-infra}"; CT='Content-Type: application/json'
pass=0; fail=0
dc(){ (cd "$COMPOSE_DIR" && docker compose "$@"); }
jget(){ python3 -c "import sys,json;d=json.load(sys.stdin);print(d$1)" 2>/dev/null; }
codigo(){ dc logs backend 2>&1 | grep -A3 'DEV-EMAIL' | grep -oE '[0-9]{6}' | tail -1; }
chk(){ if [ "$1" = "$2" ]; then echo "PASS  $3 ($1)"; pass=$((pass+1)); else echo "FAIL  $3 (esperado $2, obtido $1)"; fail=$((fail+1)); fi; }

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
RID=$(( ($(date +%s) % 900000) + 100000 )); D1=$((RID*10+1)); D2=$((RID*10+2))

# fixtures no container -> host
dc exec -T backend python -m scripts.gerar_cert_teste --saida /tmp/_c.pfx --senha certpass >/dev/null
dc exec -T backend python - >/dev/null <<'PY'
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
c=canvas.Canvas('/tmp/_f.pdf',pagesize=A4); w,h=A4
c.setFont('Helvetica',10); c.drawString(40,20,'Rodape ocupado - nao sobrescrever')
c.drawString(40,h-100,'Corpo'); c.showPage(); c.save()
PY
dc cp backend:/tmp/_c.pfx "$TMP/c.pfx" >/dev/null
dc cp backend:/tmp/_f.pdf "$TMP/f.pdf" >/dev/null

# dados de teste
dc exec -T db psql -U digitalizador -d digitalizador -tAc \
  "INSERT INTO registro (id, contrato, lote) VALUES ($RID, 12345, 'L1'); \
   INSERT INTO documento (id, registro_id, nr_folha, total_folhas) VALUES ($D1,$RID,1,1),($D2,$RID,1,1);" >/dev/null

# admin autentica
R=$(curl -s -X POST $B/auth/login -H "$CT" -d "{\"login\":\"$ADMIN_LOGIN\",\"senha\":\"$ADMIN_SENHA\"}"); TD=$(echo "$R"|jget "['token_desafio']"); OTP=$(codigo)
ATK=$(curl -s -X POST $B/auth/2fa -H "$CT" -d "{\"token_desafio\":\"$TD\",\"codigo\":\"$OTP\"}"|jget "['access_token']")

# certificado
CID=$(curl -s -X POST $B/certificados -H "Authorization: Bearer $ATK" -F "file=@$TMP/c.pfx" -F "senha=certpass"|jget "['id']")
[ -n "$CID" ] && { echo "PASS  certificado cadastrado (id=$CID)"; pass=$((pass+1)); } || { echo "FAIL cert"; fail=$((fail+1)); }
c=$(curl -s -o /dev/null -w '%{http_code}' -X POST $B/certificados -H "Authorization: Bearer $ATK" -F "file=@$TMP/c.pfx" -F "senha=x"); chk "$c" 400 "pfx senha errada -> 400"

# assinar (rodapé livre) + 2a assinatura
R=$(curl -s -X POST $B/documentos/$D1/assinar -H "$CT" -H "Authorization: Bearer $ATK" -d "{\"certificado_id\":$CID}")
chk "$(echo "$R"|jget "['ordem']")" "1" "1a assinatura"; chk "$(echo "$R"|jget "['carimbo_nova_folha']")" "False" "carimbo em folha existente"
R=$(curl -s -X POST $B/documentos/$D1/assinar -H "$CT" -H "Authorization: Bearer $ATK" -d "{\"certificado_id\":$CID}")
chk "$(echo "$R"|jget "['ordem']")" "2" "2a assinatura"
R=$(curl -s $B/documentos/$D1/assinaturas -H "Authorization: Bearer $ATK")
chk "$(echo "$R"|jget "['qtde_assinaturas']")" "2" "selo X assinaturas"
chk "$(echo "$R"|jget "['assinaturas_no_pdf']")" "2" "assinaturas embutidas no PDF"

# rodapé ocupado -> nova folha
curl -s -o /dev/null -X POST $B/documentos/$D2/arquivo -H "Authorization: Bearer $ATK" -F "file=@$TMP/f.pdf"
R=$(curl -s -X POST $B/documentos/$D2/assinar -H "$CT" -H "Authorization: Bearer $ATK" -d "{\"certificado_id\":$CID}")
chk "$(echo "$R"|jget "['carimbo_nova_folha']")" "True" "nova folha (rodapé ocupado)"

# download
curl -s -o "$TMP/out.pdf" $B/documentos/$D1/assinado -H "Authorization: Bearer $ATK"
chk "$(head -c4 "$TMP/out.pdf")" "%PDF" "download é PDF"
c=$(curl -s -o /dev/null -w '%{http_code}' -X POST $B/documentos/99999999/assinar -H "$CT" -H "Authorization: Bearer $ATK" -d "{\"certificado_id\":$CID}"); chk "$c" 404 "doc inexistente -> 404"

echo ""; echo "==== $pass PASS / $fail FAIL ===="
exit $fail
