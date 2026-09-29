# Autenticação e Acesso (Fase 1)

> Implementa os requisitos 1–3: senha com hash, login em 2 etapas por e-mail, confirmação de
> cadastro. Código em `backend/app` (models, schemas, services, api/v1). Data: 2026-09-23.

Escrito para: quem for consumir/estender a API de autenticação.

## Endpoints (`/api/v1`)

| Método | Rota | Descrição | Auth |
|--------|------|-----------|------|
| POST | `/usuarios` | Cria usuário (status `pendente`) e envia código de confirmação | **admin** |
| GET | `/usuarios/me` | Dados do usuário logado | access token |
| POST | `/auth/confirmar-email` | Confirma cadastro: valida código, **define a senha**, ativa | — |
| POST | `/auth/login` | **Etapa 1**: valida senha → envia OTP por e-mail → retorna `token_desafio` | — |
| POST | `/auth/2fa` | **Etapa 2**: valida OTP (com `token_desafio`) → emite `access`+`refresh` | — |
| POST | `/auth/refresh` | Rotaciona o par de tokens (revoga o refresh antigo) | refresh token |
| POST | `/auth/logout` | Revoga a sessão (refresh) | refresh token |
| POST | `/auth/esqueci-senha` | Envia código de redefinição (resposta neutra) | — |
| POST | `/auth/redefinir-senha` | Redefine a senha por código; revoga todas as sessões | — |
| POST | `/usuarios/{id}/definir-email` | Admin corrige o e-mail de um usuário **pendente** e reenvia a confirmação | **admin** |
| POST | `/auth/alterar-email` | Usuário ativo solicita troca do próprio e-mail (código ao **novo** endereço) | access token |
| POST | `/auth/confirmar-alteracao-email` | Confirma a troca de e-mail | access token |

## Fluxo de login (2 etapas)

```
POST /auth/login {login, senha}
     └─ senha OK → gera OTP (6 díg., expira em OTP_EXPIRE_MINUTES) → e-mail
     └─ retorna { token_desafio }           (JWT curto, type=2fa)
POST /auth/2fa {token_desafio, codigo}
     └─ OTP OK → { access_token, refresh_token }
```

## Decisões de segurança

- **Senha**: Argon2id (`app/core/security.py`). Nunca em texto puro (o legado guardava em `FONE2`).
- **OTP**: numérico, guardado como **HMAC-SHA256** (não em claro), com expiração e limite de tentativas
  (`OTP_MAX_TENTATIVAS`); códigos anteriores do mesmo tipo são invalidados a cada emissão.
- **Tokens**: JWT com `jti` aleatório (unicidade), `type` (`access|refresh|2fa|reset`) validado.
  Refresh guardado **hasheado** em `sessao`; refresh **rotaciona** (revoga o anterior).
- **Bloqueio**: após `MAX_LOGIN_TENTATIVAS` (5) a conta é bloqueada por `BLOQUEIO_MINUTOS` (15).
- **Cadastro**: usuário nasce `pendente`; só loga após confirmar e-mail (define a senha na confirmação).
- **Reset**: `esqueci-senha` responde sempre igual (não revela se o e-mail existe); ao redefinir,
  todas as sessões são revogadas.
- **Auditoria**: ações relevantes gravadas em `log_auditoria` (login ok/falha, 2fa, logout, reset...).

## E-mail

`app/services/email.py`: em produção usa **SMTP** (env `SMTP_*`); em dev sem SMTP, o e-mail (com o
código) é **registrado no log** (backend "console") — nunca em produção.

## Primeiro admin (bootstrap)

Sem SQL ad-hoc — use o script (usuário ativo e verificado):

```bash
docker compose exec backend python -m scripts.create_admin \
  --login admin --email admin@dominio.com.br --nome "Administrador"
# a senha é solicitada de forma oculta (ou via --senha)
```

## Testes

- Unitários (sem banco): `pytest tests/test_security.py`.
- Integração ponta a ponta (stack no ar): `bash tests/e2e_auth.sh` — cobre login 2FA, criação por
  admin, confirmação, refresh/rotação, logout e reset, além de checagens negativas (401/403).

## Destravar usuários migrados

Os usuários vindos do ETL têm e-mail placeholder `user<id>@migrado.invalid` e `senha_hash` nulo
(`status=pendente`) — o `.invalid` não recebe OTP. Fluxo para ativá-los:

```
1. Admin:   POST /usuarios/{id}/definir-email {email: <e-mail real>}
            → grava o e-mail, mantém pendente e envia o código ao novo endereço
2. Usuário: POST /auth/confirmar-email {login, codigo, nova_senha}
            → define a senha e ativa (status=ativo)
3. Usuário: login normal (2 etapas)
```

## Troca de e-mail (usuário ativo)

```
POST /auth/alterar-email {senha_atual, novo_email}     → código enviado ao NOVO e-mail
POST /auth/confirmar-alteracao-email {codigo}          → e-mail trocado (confirmado)
```

O novo e-mail fica em `codigo_verificacao.contexto` até a confirmação; a troca exige a senha atual e
prova de posse do novo endereço (código enviado a ele). Introduzido pela migration
`0002_codigo_alterar_email` (tipo `alterar_email` + coluna `contexto`).
