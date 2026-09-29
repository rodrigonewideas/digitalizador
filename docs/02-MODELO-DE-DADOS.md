# Modelo de Dados — Digitalizador Bonfim Web

> Dicionário de dados e mapeamento Firebird (legado) → PostgreSQL (novo).
> DDL canônico: [`../database/schema.sql`](../database/schema.sql). Data: 2026-09-23.

Escrito para: quem vai revisar/implementar o banco e o ETL (perfil técnico/DBA).

---

## 1. Visão geral

O schema tem 5 blocos:

1. **Segurança/acesso** — `grupo`, `usuario`, `codigo_verificacao`, `sessao`, `log_auditoria`.
2. **Catálogos** — `tipo_documento`, `tipo_documento_pagina`, `grupo_tipo_documento`,
   `indice_original`, `indice_apos_1999`, `motivo`, `caracteristica`.
3. **Storage** — `volume_storage`, `arquivo` (guarda POSIX com nome ofuscado UUID).
4. **Domínio** — `registro` (contrato), `documento`, `documento_legado`, `refugo`.
5. **Assinatura A1** — `usuario_certificado`, `assinatura` + view `vw_documento_assinaturas`.
6. **Parâmetros** — `parametro` (singleton), `parametro_usuario`.

Diagrama lógico resumido:

```
grupo ──< usuario ──< sessao / codigo_verificacao / usuario_certificado ──< assinatura
  │                                                              │
  └──< grupo_tipo_documento >── tipo_documento ──< documento >───┘
                                                     │   │
       registro ──< documento ──< arquivo           │   └──< documento_legado
          │            │                             │
          └──< refugo ─┘                        (assinatura, arquivo papel='assinado')

volume_storage ──< arquivo        parametro → volume_storage
```

---

## 2. Decisões de modelagem

| Tema | Legado | Novo | Motivo |
|------|--------|------|--------|
| Senha | texto puro em `FONE2` | `usuario.senha_hash` (Argon2id) | Segurança (req. 1) |
| Ativação | inexistente | `usuario.status` + `codigo_verificacao` | Confirmação de e-mail e 2FA (req. 2-3) |
| Flags `S`/`N` | `CHAR(1)` | `BOOLEAN` | Clareza/consistência |
| Datas | `DATE`/`"NOW"` | `TIMESTAMPTZ` | Fuso e hora corretos no Linux |
| PK | generator + trigger | `IDENTITY BY DEFAULT` | ETL insere ID legado; sequência continua depois |
| Arquivo físico | 3 colunas de caminho em `REGISTRO_IMAGE` | tabela `arquivo` (1 linha por papel) | Separar metadado de documento da guarda física |
| Nome do arquivo | `{seq} {contrato}-{hhmmss}.jpg` (rastreável) | **UUID** + nome original cifrado | Ofuscação forte (req. 7) |
| HD / drive `P:`,`K:` | `HD` (letras Windows) | `volume_storage` (raízes POSIX) | Migração Linux (req. 9) |
| Caminhos legados | — | `documento_legado` | Localizar binários na fase 3b |

---

## 3. Layout de arquivos no disco (storage POSIX)

Nome físico = UUID; caminho particionado por data + sharding dos 2 primeiros pares do UUID:

```
<volume.raiz_full>/<ano>/<mm>/<aa>/<bb>/<uuid>.<ext>       # ex: /srv/digitalizador/full/2026/09/a3/f1/a3f1c2....pdf
<volume.raiz_thumb>/<ano>/<mm>/<aa>/<bb>/<uuid>.jpg
<volume.raiz_backup>/<ano>/<mm>/<aa>/<bb>/<uuid>.<ext>
```

- O `object_key` em `arquivo` guarda o caminho **relativo** à raiz do volume.
- O disco não revela contrato/pessoa; o vínculo documento↔contrato só existe no banco.
- Servir sempre via API (checando permissão), nunca expor caminho ao navegador.

---

## 4. Mapeamento tabela a tabela (Firebird → PostgreSQL)

| Firebird | PostgreSQL | Observações |
|----------|------------|-------------|
| `GRUPO_USUARIO` | `grupo` | |
| `USUARIO` | `usuario` | senha → `senha_hash`; + `status`, `email_verificado`, `bloqueado_ate` |
| `GRUPO_TIPODOC` | `grupo_tipo_documento` | M:N grupo × tipo |
| `TIPO_DOC` | `tipo_documento` | `SITUACAO`→`ativo`, `FRENTE_VERSO`→bool |
| `TIPO_DOC_NITI` | `tipo_documento_pagina` | layout de páginas |
| `INDICE_ORIGINAL` | `indice_original` | |
| `INDICE_APOS_1999` | `indice_apos_1999` | |
| `MOTIVO` | `motivo` | |
| `CARAC` | `caracteristica` | |
| `HD` | `volume_storage` | `PASTA_GRAVACAO/THUMBNAIL/BACKUP/ALTA` → `raiz_*` |
| `PARAM` | `parametro` | singleton (1 linha, PK boolean) |
| `PARAM_USUARIO` | `parametro_usuario` | herança do fluxo de scanner |
| `REGISTRO` | `registro` | `titular/contrato/sepultado` = IDs externos (pdv_bonfim); `usu_*`→FK usuario |
| `REGISTRO_IMAGE` | `documento` + `arquivo` + `documento_legado` | metadado / físico / rastro legado |
| `REGISTRO_REFUGO` | `refugo` | |
| `SEQ_IMAGEM`, `TEMP` | — | descartados |
| (novo) | `codigo_verificacao` | OTP cadastro/2FA/reset |
| (novo) | `sessao` | refresh tokens |
| (novo) | `log_auditoria` | trilha LGPD |
| (novo) | `usuario_certificado` | certificado A1 (.pfx cifrado) |
| (novo) | `assinatura` | assinatura PAdES por documento |
| (novo) | `vw_documento_assinaturas` | selo "X assinaturas" |

---

## 5. Notas para o ETL

- Preservar PKs legadas (inserir com `OVERRIDING SYSTEM VALUE` não é necessário — as PKs são
  `BY DEFAULT`; após a carga, `ALTER TABLE ... ALTER COLUMN id RESTART WITH <max+1>`).
- Limpar padding de `CHAR(n)` (trim) e normalizar `'S'/'N'`→bool, `'NOW'`→`now()`.
- FKs órfãs: registrar em relatório de conciliação e decidir (nulificar × descartar).
- `REGISTRO_IMAGE`: criar `documento` + `documento_legado` **agora**; `arquivo` só quando os
  binários forem copiados (fase 3b). `refugada`, `auditada_*`, `guia`, `pasta` migram no `documento`.
- Usuários: `senha_hash = NULL`, `status = 'pendente'` → todos passam por reset + confirmação de e-mail.

---

## 6. Decisões (validadas em 2026-09-23)

1. **Integração com o sistema comercial:** ✅ **haverá integração.** `titular`, `contrato`,
   `sepultado`, `cessionário` são referências reais ao sistema do cliente (`pdv_bonfim`).
   - **Hoje:** acesso **direto ao banco** do cliente (`integracao_modo = 'direct_db'`).
   - **Futuro próximo:** **API REST** (`integracao_modo = 'api'`) — quando as APIs estiverem disponíveis.
   - Implementação: **camada de integração com adaptador plugável** no backend (uma interface
     `GatewayComercial` com implementações `DbGateway` hoje e `ApiGateway` depois). Segredos de
     conexão em env/secrets; `integracao_modo` e flags não-secretos em `parametro`.
2. **Produtividade:** ✅ **manter.** Campos `usuario.vlr_jpg_*` / `vlr_dg_*` preservados; painel de
   Produção volta como feature.
3. **Óbitos:** ✅ **parametrizar em `parametro`.** As diferenças do fluxo de óbitos (telas `*Ob`) são
   registradas em `parametro.config` (JSONB), sem estruturas separadas — `registro`/`documento` são
   compartilhados (o legado também usava as mesmas tabelas `REGISTRO`/`REGISTRO_IMAGE`).

> Especificar, quando formos implementar: (a) contrato de dados do `GatewayComercial` (quais campos
> resolvemos — nome do cessionário/titular/sepultado para a busca); (b) as chaves de `parametro.config`
> do fluxo de óbitos.
