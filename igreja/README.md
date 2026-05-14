# Mídia Suite (igreja)

Breve nota sobre mudanças recentes:

- Renomeado o frame de downloader para `app/frames/baixar_videos.py` com a classe `BaixarFrame` (antes `youtube.py`).
- Adicionado seletor de serviço na mesma aba de download: **YouTube** / **Instagram**.
- A seleção de qualidade aparece apenas para **YouTube** quando o formato "Vídeo" está selecionado.
- O botão "Abrir local do arquivo" agora prioriza a pasta escolhida em Configurações e tenta selecionar o arquivo baixado quando possível.

Como testar rapidamente:

1. Instale dependências: `pip install -r requirements.txt` (ou, no mínimo, `pip install yt-dlp` para a aba de download).
2. Rode a app: `python -m app.main`.
3. Vá em **⬇️  Baixar**, altere o "Serviço" entre **YouTube** e **Instagram**, cole uma URL e faça um download de teste.
4. Após finalizar, clique em **Abrir local do arquivo**: a pasta escolhida em *Configurações* deverá abrir (e o arquivo deverá ser selecionado no Windows).

Observações:
- O backend usa `yt-dlp` para downloads (já compatível com Instagram). Alguns formatos podem requerer um runtime JS (veja warnings do `yt-dlp`).
- Se quiser, crio um changelog mais detalhado e faço o push para o repositório remoto.

## Auto-update

O app agora pode verificar atualizações automaticamente no executável Windows.

Configuração:

1. Atualize `APP_VERSION` em `app/version.py`.
2. Faça commit das mudanças.
3. Crie e envie uma tag como `v1.0.1`.
4. O GitHub Actions vai buildar o app e publicar `Igreja.exe` na release automaticamente.

No `config.json`, o fluxo com GitHub Releases usa:

```json
{
  "github_update_repo": "matheussep17/python2",
  "github_update_asset_name": "Igreja.exe",
  "auto_check_updates": true,
  "yt_dlp_auto_update": true,
  "yt_dlp_check_interval_hours": 24
}
```

Se preferir, ainda é possível usar um manifesto externo com `update_manifest_url`.

Exemplo:

```json
{
  "version": "1.0.1",
  "url": "https://seu-servidor.com/downloads/Igreja.exe",
  "notes": "Melhorias gerais e correcoes."
}
```

O app pode checar isso ao abrir e também oferece o botão `Atualizar`.

### Atualizacao do yt-dlp

A aba de download tambem pode atualizar o `yt-dlp` separadamente do executavel. Ao abrir a tela, o app verifica no maximo uma vez por dia se existe uma versao nova no PyPI. Se houver, baixa o wheel oficial, extrai em uma pasta do usuario e passa a carregar essa versao antes da versao embutida no `.exe`.

No Windows, o pacote externo fica em:

```text
%LOCALAPPDATA%\Igreja\runtime\yt-dlp\versions
```

Se a atualizacao externa falhar, o aplicativo continua usando o `yt-dlp` embutido no executavel. A tela tambem tem o botao `Atualizar yt-dlp` para forcar a verificacao manualmente.

### Fluxo automatico de release

Depois de configurar o repositório com este workflow, a rotina fica:

```powershell
git add .
git commit -m "Release 1.0.1"
git push origin main
git tag v1.0.1
git push origin v1.0.1
```

Ao receber a tag, o GitHub executa `.github/workflows/release.yml`, gera `dist/Igreja.exe` e anexa o arquivo na release.

### Build local do executavel

Para evitar builds intermitentes com dependencias faltando, o empacotamento agora segue estas regras:

1. Crie a `.buildvenv` a partir de um CPython completo no Windows, com suporte a Tk/Tcl.
2. Rode `powershell -ExecutionPolicy Bypass -File .\build.ps1`.
3. O script valida `tkinter`, `Tcl`, `ttkbootstrap`, `tkinterdnd2`, `pip check` e o executavel final antes de concluir.
4. Se algum required critico nao entrar no `.exe`, a build falha em vez de gerar um artefato quebrado.

Observacoes importantes:

- A pasta `dist/` continua ignorada no Git. O binario final deve sair da release automatica, nao de commit manual do `.exe`.
- Se aparecer erro de `init.tcl` ou `Tcl`, recrie a `.buildvenv` usando uma instalacao do Python que realmente tenha a pasta `tcl/` completa.
- O workflow `.github/workflows/release.yml` continua sendo o caminho recomendado para publicar novas versoes com `Igreja.exe`.

## Licenciamento por computador

Foi adicionada uma camada opcional de licenciamento sem mexer nas funcionalidades internas do executável.

Como funciona:

1. O `exe` continua com as mesmas telas e fluxos.
2. Quando `license_enforced=true` no `config.json`, o app exige ativação antes de abrir a interface principal.
3. O servidor vincula o `login` ao primeiro computador que ativar.
4. Se copiarem o `exe` para outro PC, a validação falha.
5. Licenças podem ser permanentes ou com validade.

Configuração no `config.json`:

```json
{
  "license_enforced": true,
  "license_api_url": "https://seu-servidor/api/v1",
  "license_request_timeout_seconds": 10,
  "license_offline_grace_hours": 175200,
  "license_send_device_name": false,
  "license_bypass_machine_names": [
    "nome-do-note-da-igreja"
  ],
  "license_bypass_device_fingerprints": [
    "fingerprint-do-pc-autorizado"
  ]
}
```

Se `license_enforced` estiver `false`, o app abre normalmente como hoje.
Se quiser manter apenas o seu computador liberado e exigir licença nos demais, deixe `license_enforced=true` e adicione só o fingerprint da sua máquina em `license_bypass_device_fingerprints`.
Se for mais prático, também dá para liberar um equipamento pelo nome do Windows usando `license_bypass_machine_names`.
Com `license_offline_grace_hours` em `175200`, a máquina ativada continua funcionando por cerca de 20 anos mesmo sem falar com o servidor novamente.

### Servidor de licenças

Arquivos:

- `licensing_server/server.py`: API FastAPI para ativar e validar licenças.
- `licensing_server/db.py`: banco SQLite e regras de vínculo do dispositivo.
- `licensing_server/requirements.txt`: dependências do servidor.

Para subir localmente:

```powershell
pip install -r licensing_server/requirements.txt
$env:IGREJA_ADMIN_TOKEN="troque-por-um-token-forte"
uvicorn licensing_server.server:app --host 0.0.0.0 --port 8787
```

Se quiser forçar a pasta onde o arquivo local da licença será salvo, use a variável de ambiente:

```powershell
$env:IGREJA_LICENSE_STORAGE_DIR="D:\\Licencas\\Igreja"
```

Painel web:

- Abra `http://SEU-SERVIDOR:8787/admin`
- Informe o token definido em `IGREJA_ADMIN_TOKEN`
- O painel permite criar, listar, revogar, reativar, resetar dispositivo, alterar validade e excluir licenças
- O painel tambem permite exportar e anonimizar dados de uma licença para atendimento de solicitações de privacidade

### Publicar no Render com domínio próprio

Se você quiser que o app valide licenças de qualquer rede, publique o servidor em uma URL pública em vez de usar um IP local `192.168.x.x`.

Este repositório já inclui um [render.yaml](./render.yaml) pronto para isso.

Fluxo recomendado:

1. Suba este projeto para um repositório GitHub.
2. Crie uma conta em `https://render.com/`.
3. No Render, clique em `New` -> `Blueprint`.
4. Selecione o repositório deste projeto.
5. Confirme a criação do serviço `igreja-license-server`.
6. No Render, defina a variável secreta `IGREJA_ADMIN_TOKEN` com uma senha forte.
7. Aguarde o primeiro deploy terminar.
8. Teste a URL pública do serviço em `/health`.
9. Abra `/admin`, informe o token e crie as licenças.

Detalhes importantes:

- O `render.yaml` já define `uvicorn licensing_server.server:app --host 0.0.0.0 --port $PORT`.
- O serviço usa `healthCheckPath: /health`.
- O banco SQLite fica em `/var/data/licenses.db`.
- O disco persistente do Render é necessário para não perder as licenças após reinícios e deploys.

Configuração do domínio no Render:

1. No serviço criado no Render, vá em `Settings` -> `Custom Domains`.
2. Adicione `licenca.seudominio.com`.
3. O Render vai mostrar o destino DNS que deve ser configurado.
4. Depois da configuração DNS, clique em `Verify`.

Configuração DNS no hPanel/Hostinger:

1. Vá em `hPanel` -> `Domains`.
2. Clique em `Manage` ao lado do domínio.
3. Abra `DNS / Nameservers`.
4. Crie um registro `CNAME`:
   - Nome: `licenca`
   - Destino: o host informado pelo Render
5. Se houver registro `AAAA` para esse subdomínio, remova.
6. Aguarde a propagação e valide no Render.

Depois do domínio funcionar, troque no `config.json`:

```json
{
  "license_api_url": "https://licenca.matheustorres.dev/api/v1"
}
```

### Gerador / administrador de licenças

O gerador foi implementado como CLI:

```powershell
python scripts/license_admin.py create --days 365 --notes "Notebook sala 1"
python scripts/license_admin.py create
python scripts/license_admin.py list
python scripts/license_admin.py revoke IGREJA-ABC123
python scripts/license_admin.py reactivate IGREJA-ABC123
python scripts/license_admin.py reset-device IGREJA-ABC123
python scripts/license_admin.py extend IGREJA-ABC123 --days 30
python scripts/license_admin.py export-data IGREJA-ABC123
python scripts/license_admin.py anonymize IGREJA-ABC123 --reason "solicitacao do titular"
python scripts/license_admin.py purge-inactive --retention-days 1095
```

Para descobrir rapidamente a identificação do notebook que precisa ser liberado:

```powershell
python scripts/show_device_fingerprint.py
```

Ou abra o app no computador bloqueado e use o botão `Copiar identificação` na tela de ativação.

Recomendação prática:

- Use licença permanente para a maioria dos casos.
- Use validade quando quiser controle de renovação.
- Use `reset-device` quando o usuário trocar de computador.

## LGPD

O projeto inclui controles tecnicos de apoio a LGPD no licenciamento: minimizacao do nome do dispositivo, aviso na tela de ativacao, endpoint publico `/privacy`, exportacao, anonimizacao e purga de licencas inativas.

Veja o plano operacional em [docs/LGPD.md](docs/LGPD.md). A conformidade completa ainda depende de definicoes juridicas e operacionais do controlador, como base legal, encarregado/canal de atendimento, politica de privacidade, contratos e resposta a incidentes.
