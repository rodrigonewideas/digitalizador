# frontend/

SPA do Digitalizador Bonfim — **React + TypeScript + Vite**.

## Rodar em desenvolvimento

Requer o backend no ar (ver `infra/`). A URL da API é configurável:

```bash
cd frontend
cp .env.example .env          # ajuste VITE_API_URL se necessário
npm install
npm run dev                   # http://localhost:5173
```

Por padrão aponta para `http://localhost:18080/api/v1` (o backend do docker-compose).
O backend já libera CORS para `http://localhost:5173`.

Login: **admin / Senha@123**. Como o 2FA envia o código por e-mail e em dev não há SMTP, pegue o
código no log:

```bash
cd infra && docker compose logs backend | grep -A3 DEV-EMAIL | tail
```

## Estrutura

```
src/
  main.tsx            # entrypoint (Router + AuthProvider)
  App.tsx             # rotas (login / consulta / registro / certificados)
  styles.css          # design system (verde institucional, tema claro/escuro)
  api/
    client.ts         # fetch com token + refresh automático
    types.ts          # tipos da API
  auth/auth.tsx       # contexto de autenticação (login 2 etapas)
  components/Layout.tsx
  pages/
    LoginPage.tsx        # login + 2FA
    ConsultaPage.tsx     # busca por lote/contrato/registro
    RegistroPage.tsx     # documentos: anexar, comentário/refugo, assinar, baixar
    CertificadosPage.tsx # certificados A1 (upload + lista)
```

## Build

```bash
npm run build     # tsc -b + vite build  →  dist/
npm run preview   # serve o build em http://localhost:5173
```
