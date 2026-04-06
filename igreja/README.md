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
  "auto_check_updates": true
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
