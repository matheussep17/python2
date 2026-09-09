$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "Nenhum Python válido foi encontrado. Crie/ative o ambiente virtual do projeto antes de rodar os testes."
    }
    $venvPython = $pythonCommand.Source
}

Set-Location $repoRoot
& $venvPython -m unittest discover -s tests -q
exit $LASTEXITCODE
