# Testes E2E com Playwright

## Pré-requisitos

Na pasta `frontend/`:

```powershell
npm install
npx playwright install chromium
```

O frontend deve estar rodando em `http://127.0.0.1:5173/`:

```powershell
npm run dev -- --host 127.0.0.1
```

## Executar

Em outro terminal:

```powershell
npm run test:e2e
```

Os testes usam respostas controladas da API para validar a interface de forma determinística. Eles cobrem dashboard, saldo negativo, navegação, validação inline de membro e as opções financeiras `Entrada` e `Saída`.

Para executar com navegador visível:

```powershell
npx playwright test --headed
```

Para abrir o relatório de uma execução:

```powershell
npx playwright show-report
```