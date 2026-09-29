# Assinatura Digital A1 (Fase b)

> Implementa os requisitos 4–6: assinar documentos com certificado A1, carimbo no rodapé da última
> folha (nova folha se não couber), histórico e selo "X assinaturas". Data: 2026-09-24.

Escrito para: quem for consumir/estender a assinatura e a guarda de arquivos.

## Peças

| Camada | Arquivo | Papel |
|--------|---------|-------|
| Storage POSIX | `app/services/storage.py` | Guarda em disco: nome **UUID** + sharding `ano/mm/aa/bb`; registra em `arquivo` (checksum SHA-256) |
| Certificado A1 | `app/services/certificado_service.py` | Upload `.pfx`, extrai metadados; **.pfx e senha cifrados** (Fernet) |
| Assinatura | `app/services/assinatura_service.py` | PAdES via **pyHanko**; carimbo/nova folha; múltiplas assinaturas |
| API | `app/api/v1/certificados.py`, `documentos.py` | Endpoints |

## Endpoints (`/api/v1`)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/certificados` (multipart: `file`,`senha`) | Cadastra certificado A1 do usuário |
| GET | `/certificados` | Lista os certificados do usuário |
| POST | `/documentos/{id}/arquivo` (multipart: `file`) | Anexa o arquivo base (papel=full) |
| POST | `/documentos/{id}/assinar` `{certificado_id}` | Assina o documento |
| GET | `/documentos/{id}/assinaturas` | Selo "X assinaturas" + detalhes + `assinaturas_no_pdf` |
| GET | `/documentos/{id}/assinado` | Baixa o PDF assinado (última revisão) |

## Regras de carimbo (req. 5)

1. Toma o PDF base do documento (assinatura anterior → PDF full → senão gera um PDF a partir dos
   metadados).
2. **Detecta conteúdo no rodapé** da última página (banda de 72pt, via pdfminer). Se **livre**,
   carimba ali (`carimbo_nova_folha=false`). Se **ocupado** (ex.: imagem cobrindo a página),
   **acrescenta uma nova última folha** e carimba nela (`carimbo_nova_folha=true`) — sem sobrescrever.
3. Assina com pyHanko (PAdES). Cada assinatura é uma **revisão incremental** → preserva as anteriores.
   `assinaturas_no_pdf` confirma a contagem lida do próprio PDF.

## Segurança

- Nome físico = UUID (nada de contrato/nome no caminho); vínculo documento↔arquivo só no banco.
- `.pfx` e a senha do certificado **cifrados em repouso** (Fernet, chave derivada da `SECRET_KEY`;
  em produção, use uma `ENCRYPTION_KEY` dedicada).
- Certificado expirado → recusa a assinatura (409).
- Toda assinatura gera registro em `assinatura` (imutável) e `log_auditoria`.

## Limitações atuais (a evoluir)

- **Validação de cadeia/ICP-Brasil não é feita** (status gravado como `valida` = assinatura aplicada,
  não confiança da cadeia). Integrar trust store ICP-Brasil + OCSP/CRL e, idealmente, **carimbo do
  tempo (PAdES-LTA)**.
- Documentos-imagem (JPG) ainda não são **embrulhados em PDF** para assinar; hoje assina PDF (upload
  ou base gerada). O wrapping imagem→PDF entra com a fase 3b (binários reais).
- Empilhamento de muitos carimbos numa mesma folha tem espaço finito (documentado).

## Utilitários / testes

- Gerar um `.pfx` de teste (DEV): `python -m scripts.gerar_cert_teste --saida /tmp/teste.pfx --senha 123`.
- Integração ponta a ponta: `bash tests/e2e_assinatura.sh` (stack no ar + admin criado).
