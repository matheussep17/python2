# Testes

Esta pasta reúne os testes automatizados do projeto organizados por categoria:

- `test_runtime_and_config.py`: runtime, configuração e licenciamento local
- `test_updater_and_licensing.py`: validações de update e fluxo de licenças
- `test_ffmpeg_and_self_update.py`: FFmpeg e atualização automática no Windows
- `test_updater_security.py`: segurança e integridade do processo de download/atualização
- `test_device_fingerprint.py`: identidade do computador e fingerprints
- `test_license_*.py`: configurações e migração de licenças
- `test_baixar_videos_*.py`: regras do downloader/FFmpeg

Comando recomendado para rodar toda a suíte:

```powershell
cd c:/Repositorio/python2/igreja
./run_tests.ps1
```

Ou, se preferir executar diretamente:

```powershell
cd c:/Repositorio/python2/igreja
./.venv/Scripts/python.exe -m unittest discover -s tests -q
```

Observações:
- Use o ambiente virtual do projeto para garantir dependências consistentes.
- A suíte é executada com `unittest`, que é o padrão do repositório.
- Sempre valide a suíte completa antes de encerrar mudanças relevantes.
- O script `run_tests.ps1` centraliza a execução e evita variações de ambiente entre máquinas.
