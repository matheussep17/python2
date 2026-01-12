# Mídia Suite (igreja)

Breve nota sobre mudanças recentes:

- Renomeado o frame de downloader para `app/frames/baixar_videos.py` com a classe `BaixarFrame` (antes `youtube.py`).
- Adicionado seletor de serviço na mesma aba de download: **YouTube** / **Instagram**.
- A seleção de qualidade aparece apenas para **YouTube** quando o formato "Vídeo" está selecionado.
- O botão "Abrir local do arquivo" agora prioriza a pasta escolhida em Configurações e tenta selecionar o arquivo baixado quando possível.

Como testar rapidamente:

1. Instale dependências: `pip install -r requirements.txt` ou pelo menos `pip install yt-dlp`.
2. Rode a app: `python -m app.main`.
3. Vá em **⬇️  Baixar**, altere o "Serviço" entre **YouTube** e **Instagram**, cole uma URL e faça um download de teste.
4. Após finalizar, clique em **Abrir local do arquivo**: a pasta escolhida em *Configurações* deverá abrir (e o arquivo deverá ser selecionado no Windows).

Observações:
- O backend usa `yt-dlp` para downloads (já compatível com Instagram). Alguns formatos podem requerer um runtime JS (veja warnings do `yt-dlp`).
- Se quiser, crio um changelog mais detalhado e faço o push para o repositório remoto.
