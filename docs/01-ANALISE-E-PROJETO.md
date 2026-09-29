# Digitalizador Bonfim Web v1.0 — Análise do Legado e Projeto do Sistema Novo

> Documento de entendimento e desenho inicial do projeto.
> Base analisada: `/mnt/documentos_rh/bonfim/anexo/digitalizador` (script DDL Firebird, dump de dados
> e fontes Delphi 5). Versão legado identificada: **Digitalizador NITI v1.02** — Cemitério Parque
> Serra do Bonfim (CPSB), integração "New Ideas Consultoria em TI".
> Data: 2026-09-23.

---

## 1. Sumário executivo

O sistema legado é um **software de digitalização e guarda de documentos** de um cemitério
(contratos de jazigos/sepultamento). Ele indexa documentos escaneados a **contratos** (`REGISTRO`),
guarda os arquivos em **HDs/volumes físicos** com nome de arquivo trocado, e controla
**produção, auditoria e refugo** das imagens.

- **Stack legado:** Delphi 5 (VCL) + Firebird/Interbase (`.gdb`) + Windows (caminhos `P:\`, `K:\`, drives).
- **Alvo:** aplicação **WEB** em **Python + PostgreSQL** rodando em **Linux**.
- **Volume real de dados** (contado no dump):
  - `REGISTRO_IMAGE` ≈ **502.718** imagens/documentos digitalizados
  - `REGISTRO` ≈ **25.455** contratos/registros
  - `REGISTRO_REFUGO` ≈ **14.499** refugos
  - `USUARIO` = 62 · `TIPO_DOC` = 108 · `GRUPO_USUARIO` = 3 · `HD` = 1 · `MOTIVO` = 19
  - `SEQ_IMAGEM` = 426.306 (tabela auxiliar de geração de sequência — **descartável** na migração)

**Importante:** o dump de 606 MB contém apenas **metadados e caminhos**. Os **binários das imagens
(~500 mil arquivos)** estão nos volumes/HDs físicos e precisam ser localizados e migrados à parte.

---

## 2. O sistema legado (AS-IS)

### 2.1. Domínio de negócio

Cada **`REGISTRO`** representa um **contrato de jazigo** e carrega: titular, contrato, sepultado,
índices de arquivamento (original e pós-1999), datas de emissão, último ano pago, lote, e campos
de controle de processo (quem digitalizou, quem ajustou, conferências). A cada registro anexam-se
**vários documentos digitalizados** (`REGISTRO_IMAGE`), classificados por **tipo de documento**
(`TIPO_DOC`), com frente/verso e nº de folha.

### 2.2. Fluxo principal (confirmado nas telas e nos fontes)

1. **Filtrar contrato** por `Nr.Lote`, `Contrato`, `ID do Contrato` ou `Cessionário`
   (tela "Painel de Manipulação de Documentos").
2. **Anexar** — lê uma pasta de digitalização (ex.: `D:\SCANNER\KAMILA\<timestamp>\`), copia os
   arquivos para o volume de guarda **renomeando-os**, gera thumbnail e cópia de backup.
3. **Alterar** anexos, **Refugar** (rejeitar imagem com motivo) e **Excluir Anexos**.
4. **Auditoria** (`AUDITA_IMAGEM`, campos `AUDITADA_EM/POR`) e **Produção** (painéis de acompanhamento
   por usuário/período — os campos `VLR_JPG_*` sugerem apuração de produtividade/pagamento por lote).
5. Fluxo separado para **Óbitos** (telas/units com sufixo `Ob`).

### 2.3. Menu do sistema

`Tabelas` (Grupo de Usuários, Usuários, Tipo de Documentos, Índice Original, Índice Após 1999,
Motivo, Parâmetros) · `Digitalizar` · `Digitalizar Óbitos` · `Auditoria` · `Produção` ·
`Integra Base` · `Sair`.

### 2.4. Modelo de guarda de arquivos (o "conceito de local de guarda")

Caminho real observado no dump:

```
IMAGE (full):  P:\08142008\FULL\297 19257-144612.jpg
THUMBNAIL:     P:\08142008\THM\THM297 19257-144612.jpg
BACKUP:        K:\08142008\BKP\BKP297 19257-144612.jpg
NOME_ARQ_TEMP (nome original do scanner): 000004.JPG
```

Decompondo o nome físico `297 19257-144612.jpg`:
- `297` = `SEQ_IMAGEM` (sequência global do banco)
- `19257` = número do `CONTRATO`
- `144612` = `HHMMSS` do momento da gravação

Regras de armazenamento (tabelas `HD` e `PARAM`):
- **`HD`** cadastra cada volume físico com pastas de `GRAVACAO`, `BACKUP`, `THUMBNAIL` e `ALTA`
  (ex.: `P:` grava, `K:` backup). Cada imagem guarda `ID_HD_IMAGE`, `ID_HD_BACKUP`, `ID_HD_THUMBNAIL`.
- **`PARAM`** aponta o HD "ativo" para gravação/backup/thumbnail e a `LOCACAO_ATUAL`.
- O **nome original** do arquivo é descartado do caminho e preservado só em `NOME_ARQ_TEMP` — este
  é o embrião do requisito de **"trocar o nome para não dar rastreabilidade"**. Hoje a ofuscação é
  **fraca** (o nome ainda embute o número do contrato + data).

### 2.5. Segurança do legado — dívidas críticas encontradas

| # | Problema | Evidência |
|---|----------|-----------|
| 1 | **Senha em texto puro** no banco: o login compara a senha digitada diretamente com o campo `FONE2`. | `U_LOGON.PAS:264` `if sqlUsuariofone2.asstring <> edtSenha.text` |
| 2 | Senhas do **SYSDBA hardcoded** no cliente (`masterkery`, `bonfim2005`, `+x+KEEyi`). | `U_LOGON.PAS:207-213` |
| 3 | **Sem 2FA**, sem confirmação de e-mail, sem hash. Bloqueio só por 3 tentativas locais. | `U_LOGON.PAS:300` |
| 4 | Caminhos e drives **Windows** hardcoded; acesso ao banco por IP fixo em `.ini`. | `nitidig.ini`, `arqini.ini` |
| 5 | Fontes com **código morto / handlers de debug** (`showMessage('teste...')`) em produção. | `u_AnexaAltera.pas` |

Esses pontos justificam diretamente os requisitos do sistema novo (auth forte, 2FA, hash de senha).

### 2.6. Modelo de dados legado (Firebird)

Tabelas principais e papel:

- **`USUARIO`** — usuários (login único, nome, administrador S/N, situação, grupo, e-mail, `TENTATIVA`,
  `ACESSO_CANCELADO`). Senha hoje "escondida" em `FONE2`.
- **`GRUPO_USUARIO`** / **`GRUPO_TIPODOC`** — grupos e quais tipos de documento cada grupo enxerga (RBAC embrionário).
- **`TIPO_DOC`** / **`TIPO_DOC_NITI`** — catálogo de tipos de documento (frente/verso, qtde de folhas, situação, página inicial).
- **`REGISTRO`** — contrato/jazigo (titular, contrato, sepultado, índices, datas, lote, conferências).
- **`REGISTRO_IMAGE`** — documento digitalizado (tipo_doc, frente, folha, caminhos full/thumb/backup,
  HDs, extensão, tamanho, máquina/volume de origem, auditoria, refugo, guia, pasta).
- **`REGISTRO_REFUGO`** — refugos com motivo, comentário, resolução.
- **`HD`** — volumes físicos de guarda. **`PARAM`** — parâmetros globais de gravação. **`PARAM_USUARIO`** — última pasta lida / apaga origem.
- **`INDICE_ORIGINAL`**, **`INDICE_APOS_1999`**, **`MOTIVO`**, **`CARAC`** — tabelas de apoio.
- **`SEQ_IMAGEM`**, **`TEMP`** — auxiliares técnicas (descartáveis).
- 15 generators + triggers `BEFORE INSERT` para PKs (equivalem a `SEQUENCE`/`IDENTITY` no PostgreSQL).
- 1 view (`REGISTRO_LIMPO`) e 2 stored procedures relevantes (`AUDITA_IMAGEM` + geradores de ID).

---

## 3. O sistema novo (TO-BE)

### 3.1. Requisitos (extraídos do briefing)

1. **Login com senha criptografada** (hash) no banco.
2. **Login em 2 etapas (2FA)** usando **e-mail** como conferência.
3. **Confirmação de e-mail no cadastro** — usuário fica *pendente de ativação* até confirmar o código.
4. **Assinatura digital A1** por usuário (certificado `.pfx`/PKCS#12) para **assinar documentos**,
   com **histórico de assinaturas**.
5. **Carimbo no rodapé da última folha** do documento assinado, **sem sobrescrever texto**
   (se não couber, acrescentar nova última folha).
6. Nas **consultas**, deixar claro que o documento tem **X assinaturas**, com **detalhes** abríveis.
7. **Guarda de qualquer tipo de arquivo**, com **troca do nome original** (ofuscação, sem rastreabilidade).
8. **Repensar o conceito de local de guarda** e estrutura dos arquivos com base nos dados reais.
9. **Migrar de Windows para Linux** — tratar caminhos, acessos e credenciais.

### 3.2. Arquitetura proposta (visão macro)

```
┌──────────────┐   HTTPS   ┌─────────────────────┐        ┌──────────────────┐
│  Navegador   │ ───────▶ │  Nginx (reverse      │ ─────▶ │  API Python       │
│  React SPA   │          │  proxy + TLS)        │        │  (FastAPI)        │
└──────────────┘          └─────────────────────┘        └───────┬──────────┘
                                                                  │
                          ┌───────────────────────────────────────┼───────────────┐
                          ▼                     ▼                  ▼               ▼
                  ┌───────────────┐   ┌──────────────────┐  ┌────────────┐  ┌───────────┐
                  │ PostgreSQL 16 │   │ Storage FS POSIX  │  │  Worker    │  │  SMTP     │
                  │ (metadados)   │   │ (disco/mount):    │  │ (fila:     │  │ (e-mail   │
                  │               │   │ full/thumb/backup │  │ thumbs,    │  │  2FA)     │
                  └───────────────┘   └──────────────────┘  │ assinatura)│  └───────────┘
                                                            └────────────┘
```

> **Decisões fechadas (2026-09-23):** Backend **FastAPI** · Frontend **React SPA + TypeScript** ·
> Storage em **sistema de arquivos POSIX** (não object storage) · **HDs físicos disponíveis** —
> migraremos o conteúdo real das imagens.

Componentes na estrutura de pastas já existente no repositório:
- **`backend/`** — API Python (regras de negócio, auth, assinatura, storage).
- **`frontend/`** — aplicação web (consulta, digitalização, assinatura, painéis).
- **`database/`** — schema PostgreSQL + migrations.
- **`etl/`** — migração de dados Firebird → PostgreSQL e realocação dos binários.
- **`infra/`** — Docker Compose, Nginx, MinIO, configs de deploy Linux.
- **`docs/`** — este e demais documentos de projeto.

### 3.3. Stack tecnológico proposto (recomendação — a confirmar na seção 6)

| Camada | Recomendação | Por quê |
|--------|--------------|---------|
| Linguagem | Python 3.12 | Requisito do projeto |
| API | **FastAPI** + Pydantic v2 | Assíncrono, tipado, OpenAPI automático; ótimo para upload/streaming de arquivos |
| ORM/migrations | SQLAlchemy 2 + Alembic | Padrão de mercado, migrations versionadas |
| Banco | **PostgreSQL 16** | Requisito do projeto |
| Storage | **Sistema de arquivos POSIX** (disco/mount no servidor) | Decisão fechada; raízes de disco fazem o papel dos HDs legados (full/thumb/backup) |
| Auth | JWT + refresh; hash **Argon2id**; 2FA por **OTP via e-mail** | Atende req. 1–3 |
| Assinatura | **pyHanko** (PAdES) + `cryptography` | Assina PDF com A1 (`.pfx`), carimbo visual, LTV |
| Fila/worker | Celery ou RQ + Redis | Thumbnails, assinatura em lote, e-mails assíncronos |
| Frontend | **React (Vite) + TypeScript** | Visualizador de documentos e painéis ricos |
| Deploy | Docker Compose + Nginx (TLS) em Linux | Req. 9 |

### 3.4. Novo modelo de dados (PostgreSQL) — princípios e mapeamento

Princípios: `snake_case`, PKs `BIGSERIAL`/`IDENTITY`, `created_at/updated_at`, FKs explícitas,
`CHAR(1)` de flag → `BOOLEAN`, campos de senha **fora** de `FONE2`.

Mapeamento resumido legado → novo:

| Firebird | PostgreSQL (proposto) | Observações |
|----------|----------------------|-------------|
| `USUARIO` | `usuario` | + `senha_hash`, `email_verificado`, `status` (pendente/ativo/bloqueado), `certificado_a1` (ref.), remover senha de `FONE2` |
| `GRUPO_USUARIO`, `GRUPO_TIPODOC` | `grupo`, `grupo_tipo_doc` | Base do RBAC |
| `TIPO_DOC`, `TIPO_DOC_NITI` | `tipo_documento` | |
| `REGISTRO` | `registro` (contrato) | Mantém FKs de titular/sepultado/índices |
| `REGISTRO_IMAGE` | `documento` + `arquivo` | **Separar** metadado do documento da localização física do arquivo |
| `REGISTRO_REFUGO` | `refugo` | |
| `HD`, `PARAM`, `PARAM_USUARIO` | `volume_storage`, `parametro` | HD físico → raiz de disco/mount POSIX (full/thumb/backup) |
| `INDICE_*`, `MOTIVO`, `CARAC` | idem (tabelas de apoio) | |
| `SEQ_IMAGEM`, `TEMP` | — | Descartar (sequências viram `IDENTITY`) |

**Novas tabelas** para os requisitos novos:
- `usuario_certificado` — certificado A1 do usuário (referência ao arquivo cifrado, validade, titular).
- `assinatura` — cada assinatura aplicada a um documento (quem, quando, hash do doc, posição do carimbo, referência ao PDF assinado, cadeia/OCSP).
- `assinatura_historico` / auditoria — trilha imutável.
- `verificacao_email` / `otp` — códigos de confirmação de cadastro e de 2FA (com expiração).
- `arquivo` — abstração de storage (bucket, object key ofuscado, checksum, tamanho, mime, tipo=full/thumb/backup, nome_original cifrado).
- `log_auditoria` — trilha de acessos e ações (LGPD).

### 3.5. Autenticação, cadastro e 2FA (req. 1–3)

- **Cadastro:** admin cria usuário → status `PENDENTE` → e-mail com código/link de confirmação → ao
  confirmar, status `ATIVO`. Sem confirmar, não loga.
- **Senha:** hash **Argon2id** (nunca reversível; migração antiga marca todos para *reset* obrigatório —
  ver §4.3).
- **2FA (2 etapas):** senha correta → gera **OTP de 6 dígitos** enviado por e-mail (expira em ~5 min,
  rate-limit e nº de tentativas) → valida → emite JWT.
- **Bloqueio:** contador de tentativas + `acesso_cancelado` migrados; desbloqueio por admin.

### 3.6. Assinatura digital A1 (req. 4–6)

- **Certificado A1:** upload do `.pfx` (PKCS#12) do usuário, **armazenado cifrado** (a senha do
  certificado nunca em texto puro); validade e titular registrados.
- **Assinatura de PDF:** usar **pyHanko** para assinatura PAdES. Documentos-imagem (JPG/TIFF) são
  **convertidos/embrulhados em PDF** antes de assinar.
- **Carimbo no rodapé da última página, sem sobrescrever texto:**
  1. medir a área ocupada da última página;
  2. se houver espaço livre no rodapé → desenhar o carimbo (assinante, data/hora, validade) ali;
  3. se **não** couber → **acrescentar nova última folha** com os carimbos (conforme o briefing).
- **Múltiplas assinaturas:** cada assinatura é um novo *revision* do PDF (assinatura incremental do
  PAdES preserva as anteriores) + 1 registro em `assinatura`.
- **Consulta:** listagem mostra selo **"X assinaturas"**; ao abrir, painel de **detalhes**
  (assinante, data/hora, validade do certificado, hash, status de verificação).

### 3.7. Guarda de documentos e local de guarda (req. 7–8) — **sistema de arquivos POSIX**

Repensar o conceito de HD/pasta para **armazenamento em sistema de arquivos no Linux**, mantendo a
intenção original (gravação + backup + thumbnail + ofuscação):

- **Raízes de storage (mounts) = os "HDs" legados.** Uma tabela `volume_storage` cadastra cada raiz
  (ex.: `/srv/digitalizador/full`, `/srv/backup/digitalizador`, disco secundário/NAS), com papel
  (full/thumb/backup) e status ativo/inativo — preserva o conceito de múltiplos volumes e capacidade.
- **Ofuscação forte:** nome físico = **UUIDv4**, **sem** contrato/data/nome. O nome **original** vai
  cifrado no metadado (`arquivo.nome_original`), nunca no caminho em disco.
- **Layout em disco** particionado para não estourar diretório (evita milhões de arquivos numa pasta):
  ```
  <raiz_full>/<ano>/<mes>/<aa>/<bb>/<uuid>.<ext>        # aa,bb = 2 primeiros pares do uuid (sharding)
  <raiz_thumb>/<ano>/<mes>/<aa>/<bb>/<uuid>.jpg
  <raiz_backup>/<ano>/<mes>/<aa>/<bb>/<uuid>.<ext>
  ```
  A ligação documento↔contrato vive **só no banco** — o disco não revela nada.
- **Qualquer tipo de arquivo:** guardar `mime`, `extensao`, `checksum` **SHA-256** (integridade e
  deduplicação) e `tamanho`. Servir sempre via API (nunca expor o caminho de disco ao navegador).
- **Backup:** cópia na raiz de backup (papel do antigo `K:`), + rotina de `rsync`/snapshot no nível de SO.
- Migração dos ~500k binários (`P:\...`/`K:\...` → novo layout com UUID): ver §4 (fase à parte).

### 3.8. Windows → Linux (req. 9)

- Eliminar drives (`P:`, `K:`, `D:\SCANNER\...`) → **URIs de storage** (`s3://bucket/key`) e
  caminhos POSIX; sem letras de unidade.
- Credenciais fora do código/`.ini` → **variáveis de ambiente / secrets** (`.env`, Docker secrets).
- Conexão ao banco por serviço (`postgres:5432`), não IP fixo do cliente.
- Upload de digitalização passa a ser via **web** (o navegador envia os arquivos) em vez de o app ler
  uma pasta local de scanner — remove a dependência de máquina/volume de origem.

### 3.9. Integração com o sistema comercial (pdv_bonfim)

Os campos `titular`, `contrato`, `sepultado` e o **cessionário** (nome usado na busca) pertencem ao
**sistema comercial do cliente**, não ao Digitalizador. Haverá **integração**:

- **Hoje:** acesso **direto ao banco** do cliente → `parametro.integracao_modo = 'direct_db'`.
- **Futuro próximo:** **API REST** (ainda não disponível) → `integracao_modo = 'api'`.

Desenho: uma **camada de integração com adaptador plugável** isola o resto do sistema da origem dos
dados:

```
        Backend (regras/consulta)
                 │  usa
                 ▼
        GatewayComercial (interface)      ← resolve nome do cessionário/titular, valida contrato...
          ├── DbGateway   (hoje: lê o banco do cliente)
          └── ApiGateway  (futuro: consome a API REST)
```

- Troca de modo por configuração (`parametro.integracao_modo`), sem mexer nas regras de negócio.
- **Segredos** de conexão (DSN/URL/credenciais) ficam em **env/secrets**, nunca no banco.
- A busca por **cessionário** (tela principal do legado) é atendida pelo gateway (resolve nome →
  contratos) — a definir o contrato de dados quando formos implementar.

---

## 4. Migração de dados (ETL)

Fluxo em `etl/`:

1. **Carregar** o dump Firebird em um Firebird temporário **ou** parsear os `INSERT`s do arquivo
   `dados/Bco/digitalizador_dados` diretamente.
2. **Transformar**: normalizar tipos (`CHAR(1)`→bool, `DATE "NOW"`→timestamp), limpar padding de
   `CHAR`, resolver FKs, descartar `SEQ_IMAGEM`/`TEMP`.
3. **Carregar** no PostgreSQL (idempotente, com mapa de IDs legado→novo).
4. **Binários (fase à parte — o cliente copia os HDs depois):** a partir de
   `REGISTRO_IMAGE.IMAGE/IMAGE_THUMBNAIL/IMAGE_BACKUP` + tabela `HD`, ler os arquivos dos volumes e
   **copiar para o storage POSIX com nome ofuscado (UUID)**, no layout particionado, gravando
   `arquivo` (checksum SHA-256). Cada `documento` já é migrado **agora** com o registro do caminho
   legado; o vínculo ao arquivo físico é preenchido quando os HDs forem disponibilizados.
5. **Senhas**: não há hash a migrar (estavam em texto puro) → todos os usuários entram com
   **reset obrigatório** + reconfirmação de e-mail.
6. **Conciliação**: relatório de contagem origem×destino, arquivos ausentes, órfãos.

**Sequenciamento:** metadados migram **primeiro** (não dependem das mídias). A cópia dos **~500 mil
binários** roda numa **fase posterior**, quando os HDs forem copiados — o dump traz os caminhos, não
os bytes.

---

## 5. Roadmap sugerido por fases

| Fase | Entrega | Duração aprox. |
|------|---------|----------------|
| **0 — Fundação** | Docker Compose (Postgres + MinIO + API + Nginx), esqueleto FastAPI, CI, .env/secrets | 1 sprint |
| **1 — Modelo + Auth** | Schema PostgreSQL + Alembic; cadastro, confirmação de e-mail, senha Argon2, 2FA por e-mail, RBAC | 1–2 sprints |
| **2 — ETL metadados** | Migrar `REGISTRO`, `REGISTRO_IMAGE`, tipos, usuários, refugos; relatório de conciliação (não depende dos HDs) | 1–2 sprints |
| **3 — Storage + guarda** | Upload de qualquer arquivo, ofuscação UUID, thumbnails, raízes full/thumb/backup em disco | 2 sprints |
| **3b — Migração dos binários** | Copiar os ~500k arquivos dos HDs → storage POSIX (UUID + checksum); conciliação (quando os HDs forem disponibilizados) | 1–2 sprints |
| **4 — Consulta e digitalização web** | Busca por lote/contrato/cessionário, visualizador, anexar/alterar/refugar, auditoria e produção | 2–3 sprints |
| **5 — Assinatura A1** | Upload de certificado, assinatura PAdES, carimbo no rodapé/nova folha, histórico e selo "X assinaturas" | 2 sprints |
| **6 — Go-live** | Hardening, backup/restore, LGPD, homologação, cutover | 1–2 sprints |

---

## 6. Decisões fechadas (2026-09-23)

1. **Backend:** ✅ **FastAPI**.
2. **Frontend:** ✅ **React SPA + TypeScript**.
3. **Storage dos arquivos:** ✅ **Sistema de arquivos POSIX** (disco/mount no servidor Linux).
4. **Binários:** ✅ HDs disponíveis, porém **a cópia dos arquivos será feita depois** — migramos
   **metadados primeiro** e os binários numa fase posterior.

---

## 7. Riscos principais

- **Cópia dos binários** (~500k arquivos) fica para uma fase posterior — atenção a integridade,
  tempo de cópia e conciliação quando os HDs forem disponibilizados.
- **Qualidade/consistência** dos dados legados (padding de `CHAR`, datas nulas, FKs órfãs).
- **Certificados A1**: guarda segura da senha do `.pfx` e validade/renovação.
- **LGPD**: dados de pessoas (titulares/sepultados) exigem trilha de auditoria e controle de acesso.
- **Volume**: 500k+ arquivos exige storage e indexação bem dimensionados.

---

*Próximo passo sugerido: fechar as 4 decisões da §6 e então detalhar o **schema PostgreSQL**
(`database/`) e o **ETL** (`etl/`).*
