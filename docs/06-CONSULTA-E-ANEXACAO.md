# Consulta e Anexação de Documentos (Fase a)

> Desenho da versão web das telas de **consulta** (Painel de Manipulação) e **anexação**
> (Anexar Documentos), a partir das telas reais do legado. Data: 2026-09-24.

Escrito para: quem vai implementar/consumir a consulta e a anexação.

## 1. O que as telas do legado fazem

### 1.1 Painel de Manipulação de Documentos (consulta)
- Filtro por **Nr.Lote**, **Contrato**, **ID do Contrato**, **Cessionário**.
- Lista os **cessionários/contratos** do lote (Tipo de terreno: Gaveta/Lote/Jazigo/P.F. Ossário…,
  Contrato nº, nº da Pasta/Arquivo, código e **nome do cessionário**). Esses dados vêm do **sistema
  comercial** (pdv_bonfim), não do Digitalizador.
- Mostra as **miniaturas** das imagens já anexadas (tipo abreviado + id da imagem + `Pg/Frente`).
- Ações: **Anexar** (coletar novas imagens), **Alterar**, **Refugar**, **Excluir Anexos**.

### 1.2 Anexar Documentos (coleta)
- **Local de Origem**: uma **pasta de origem** (scanner, ex.: `S:\`) com as imagens em sequência.
- **Catálogo** de tipos de documento (esquerda) → o usuário move os tipos desejados para
  **SELECIONADOS para coleta** (`>` / `<`), e o sistema puxa as imagens **na ordem das folhas**.
- Por documento selecionado ajusta: `Ord` (ordem), `Frente/Verso?`, `É a Frente?`, `Fls`,
  `Pág Inicial`, `Dica da Frente do Documento`.
- **Gravação**: `Local de Gravação Original` (Pasta `P:`, `HD Ativo`, `Serial Volume`) e
  `Local de Gravação Backup` (`K:`), com opção **Apaga Origem**. Nº de **Pasta/Arquivo** (ex.: 117).
- **Comentários e Refugos**: por documento, marca **Motivo** (da tabela `MOTIVO`) + **Comentário**.

### 1.3 Descoberta importante — assinatura já é feita via ZapSign (ICP-Brasil)
Uma das telas mostra um **"Relatório de Assinaturas" da ZapSign (by Truora)** anexado como documento
do tipo **"Assinatura Digital"**: documento assinado por **cliente + empresa + testemunha**
("4 de 4 Assinaturas"), com validação por **código único (SMS/e-mail)**, hash SHA-256 e selo
**INTEGRIDADE CERTIFICADA – ICP-BRASIL (MP 2.200-2/2001, Lei 14.063/2020)**.

Implicação: hoje a assinatura **externa multipartes** é feita na ZapSign e o **PDF-relatório** é
guardado como um documento. A **assinatura A1** que construímos (Fase b) é um mecanismo **interno**
(certificado do usuário). São complementares — ver §5 (decisão a alinhar).

## 2. Mapeamento para o modelo já existente

| Tela | Modelo |
|------|--------|
| Catálogo de tipos | `tipo_documento` (108 tipos migrados) — `qtde_folhas`, `frente_verso`, `pagina_inicial`, `indicacao_frente` (=“dica”) |
| Motivos de refugo/comentário | `motivo` (migrado) |
| Cessionário/contrato do lote | **GatewayComercial** (pdv_bonfim) — não é do Digitalizador |
| Documento anexado | `documento` (tipo, `nr_folha`=ordem, `face`=F/V, `total_folhas`, `pasta`, `guia`) |
| Imagem física | `arquivo` (papel=full/backup/thumbnail) no storage POSIX |
| Comentário/Refugo | `refugo` (`motivo_id` opcional, `comentario`, `resolvido`) |

## 3. Endpoints da fase (implementados agora)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/tipos-documento` | Catálogo de tipos (para a lista da esquerda) |
| GET | `/motivos` | Motivos de refugo/comentário |
| GET | `/registros?lote=&contrato=&registro_id=` | Consulta: registros + **cessionário** (via gateway) + nº de documentos |
| GET | `/registros/{id}/documentos` | Documentos do registro (tipo, folha, face, nº de assinaturas, refugos) |
| POST | `/registros/{id}/documentos` | Cria/ajusta um documento (tipo, folha, face) — passo “ajustar” |
| POST | `/documentos/{id}/comentario` | Adiciona **comentário/particularidade** (motivo opcional) e/ou **refuga** |

Reaproveita da Fase b: `POST /documentos/{id}/arquivo` (anexa a imagem), `/assinaturas`, `/assinado`.

## 4. GatewayComercial (integração pdv_bonfim)
Abstração `app/services/gateway_comercial.py` (ver `docs/01 §3.9`): resolve **cessionário/contrato**
por lote. Hoje `integracao_modo='direct_db'` (a implementar a leitura real do banco do cliente);
amanhã `'api'`. Enquanto o acesso não está configurado, retorna vazio/placeholder — o restante da
consulta funciona sobre os dados já migrados (registro/documento).

## 5. Depende de / a alinhar
- **Cessionário na busca**: precisa do **GatewayComercial** conectado ao pdv_bonfim (credenciais/rota).
- **Miniaturas (thumbnails)**: dependem dos **binários** (fase 3b, quando os HDs vierem).
- **Assinatura — decisão**: manter/priorizar a **A1 interna** (Fase b), **integrar ZapSign**
  (multipartes, ICP-Brasil, como já é usado), ou os dois? Isso define o próximo reforço de assinatura.
