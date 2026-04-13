$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BuildPython = Join-Path $ProjectRoot ".buildvenv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $BuildPython)) {
    throw "Python de build nao encontrado em '.buildvenv\\Scripts\\python.exe'. Crie a .buildvenv com um CPython completo antes de empacotar."
}

Write-Host "Validando suporte a tkinter no ambiente de build..."
& $BuildPython -c "import tkinter, tkinter.ttk; print('tkinter ok:', tkinter.TkVersion)"
if ($LASTEXITCODE -ne 0) {
    throw "A .buildvenv nao consegue importar tkinter. Use um CPython com suporte a Tk."
}

if (-not $env:BUILD_SKIP_BOOTSTRAP) {
    Write-Host "Garantindo pip na .buildvenv..."
    & $BuildPython -m ensurepip --upgrade
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao inicializar o pip na .buildvenv."
    }

    Write-Host "Instalando dependencias de build..."
    & $BuildPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt") pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao instalar dependencias na .buildvenv."
    }
} else {
    Write-Host "Bootstrap de dependencias ignorado (BUILD_SKIP_BOOTSTRAP=1)."
}

$FfmpegDir = Join-Path $ProjectRoot "vendor\\ffmpeg\\bin"
$FfmpegExe = Join-Path $FfmpegDir "ffmpeg.exe"
$FfprobeExe = Join-Path $FfmpegDir "ffprobe.exe"

if (-not (Test-Path -LiteralPath $FfmpegExe)) {
    throw "FFmpeg nao encontrado em '$FfmpegExe'. Adicione ffmpeg.exe para gerar um executavel completo."
}

if (-not (Test-Path -LiteralPath $FfprobeExe)) {
    throw "FFprobe nao encontrado em '$FfprobeExe'. Adicione ffprobe.exe para gerar um executavel completo."
}

Write-Host "FFmpeg local encontrado em '$FfmpegDir'. Ele sera embutido no executavel."

Write-Host "Limpando build anterior..."
$BuildDir = Join-Path $ProjectRoot "build"
$DistDir = Join-Path $ProjectRoot "dist"

if (Test-Path -LiteralPath $BuildDir) {
    Remove-Item -LiteralPath $BuildDir -Recurse -Force
}

if (Test-Path -LiteralPath $DistDir) {
    Remove-Item -LiteralPath $DistDir -Recurse -Force
}

Write-Host "Gerando executavel..."
& $BuildPython -m PyInstaller --noconfirm (Join-Path $ProjectRoot "igreja.spec")
if ($LASTEXITCODE -ne 0) {
    throw "Falha durante o PyInstaller."
}

Write-Host "Build concluido. Executavel em 'dist\\Igreja.exe'."
