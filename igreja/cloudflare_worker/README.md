# Servidor de licencas no Cloudflare

Esta versao substitui o Railway por Cloudflare Workers + D1 e atende somente:

- `https://matheustorresqa.com/appigreja/*`

O restante do dominio continua no GitHub Pages. Nenhum arquivo ou rota de
`/casamento` precisa ser alterado.

## Arquitetura

1. O DNS do dominio fica no Cloudflare, mantendo os quatro registros `A` do
   GitHub Pages.
2. Uma rota de Worker intercepta apenas
   `matheustorresqa.com/appigreja/*`.
3. O GitHub Pages continua recebendo `/`, `/casamento` e as demais rotas.
4. O banco D1 armazena as licencas sem mensalidade para o volume atual do app.

## Publicacao

Na pasta `cloudflare_worker`:

```powershell
npm install
npx wrangler login
npx wrangler d1 create igreja-licenses
```

Copie o `database_id` exibido para `wrangler.toml` e inicialize o banco:

```powershell
npm run db:init:remote
npx wrangler secret put ADMIN_TOKEN
npm run deploy
```

No painel Cloudflare, crie uma rota de Worker:

```text
matheustorresqa.com/appigreja/*
```

Ela deve apontar para o Worker `igreja-license-server`. Nao use uma rota como
`matheustorresqa.com/*`, pois ela tambem capturaria `/casamento`.

## Migracao das licencas

O servidor FastAPI antigo possui a rota protegida:

```text
GET /api/v1/admin/backup
```

Baixe o JSON enquanto o Railway ainda estiver funcionando:

```powershell
curl.exe `
  -H "X-Admin-Token: SEU_TOKEN" `
  https://python2-production-e3ee.up.railway.app/api/v1/admin/backup `
  -o licenses-backup.json
```

Depois do deploy do Worker:

```powershell
curl.exe `
  -X POST `
  -H "Content-Type: application/json" `
  -H "X-Admin-Token: SEU_TOKEN" `
  --data-binary "@licenses-backup.json" `
  https://matheustorresqa.com/appigreja/api/v1/admin/import
```

Teste:

```powershell
curl.exe https://matheustorresqa.com/appigreja/health
```

Somente depois do teste, altere no `config.json`:

```json
{
  "license_api_url": "https://matheustorresqa.com/appigreja/api/v1"
}
```

O painel administrativo ficara em:

```text
https://matheustorresqa.com/appigreja/admin
```

## Exportacao por arquivo

Se houver acesso direto ao `licenses.db`, tambem e possivel gerar o JSON:

```powershell
python scripts/export_licenses_for_cloudflare.py CAMINHO\licenses.db
```
