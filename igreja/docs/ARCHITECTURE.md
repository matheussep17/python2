# Arquitetura do projeto

O projeto possui três responsabilidades que devem permanecer separadas:

## Aplicativo desktop

Fica em `app/` e contém a interface Tkinter, processamento de mídia, atualização
e licenciamento local. Os módulos de mídia existentes são considerados estáveis;
novas mudanças neles devem ser pequenas, testadas e isoladas.

## Serviços de licenciamento

`licensing_server/` contém a API FastAPI tradicional, enquanto
`cloudflare_worker/` contém a implementação equivalente para Cloudflare Workers
e D1. Eles compartilham o contrato da API, mas não devem importar código do
aplicativo desktop.

## Operação e distribuição

`scripts/`, `.github/workflows/`, `build.ps1` e os arquivos de deploy cuidam de
testes, empacotamento e publicação. Artefatos gerados ficam em `build/` e
`dist/`, que não devem ser versionados.

O futuro site institucional da igreja deverá ser um projeto web separado para
não aumentar o risco de regressão no aplicativo de mídia.
