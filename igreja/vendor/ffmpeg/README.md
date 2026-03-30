Coloque aqui os binarios do FFmpeg que devem acompanhar o executavel.

Estrutura esperada:

- `vendor/ffmpeg/bin/ffmpeg.exe`
- `vendor/ffmpeg/bin/ffprobe.exe`

Quando esses arquivos existirem:

- o `build.ps1` avisara que encontrou o FFmpeg local;
- o `igreja.spec` vai embutir esses binarios no `exe`;
- ao iniciar, o app adiciona a pasta do FFmpeg ao `PATH` do proprio processo antes de abrir a interface.
