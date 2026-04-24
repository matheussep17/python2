$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BuildPython = Join-Path $ProjectRoot ".buildvenv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $BuildPython)) {
    throw "Python de build nao encontrado em '.buildvenv\\Scripts\\python.exe'. Crie a .buildvenv com um CPython completo antes de empacotar."
}

Write-Host "Validando suporte a tkinter no ambiente de build..."
& $BuildPython -c "import tkinter, tkinter.ttk, ttkbootstrap, tkinterdnd2; interp = tkinter.Tcl(); print('tkinter ok:', tkinter.TkVersion); print('tcl library:', interp.eval('info library')); print('ttkbootstrap ok:', ttkbootstrap.__file__); print('tkinterdnd2 ok:', tkinterdnd2.__file__)"
if ($LASTEXITCODE -ne 0) {
    throw "A .buildvenv nao consegue inicializar tkinter/Tcl ou os pacotes de UI obrigatorios. Use um CPython com suporte completo a Tk."
}

if (-not $env:BUILD_SKIP_BOOTSTRAP) {
    Write-Host "Garantindo pip na .buildvenv..."
    & $BuildPython -m ensurepip --upgrade
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao inicializar o pip na .buildvenv."
    }

    Write-Host "Instalando dependencias de build..."
    & $BuildPython -m pip install --upgrade pip setuptools wheel
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao instalar dependencias na .buildvenv."
    }

    & $BuildPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt") pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao instalar dependencias na .buildvenv."
    }

    Write-Host "Validando consistencia das dependencias instaladas..."
    & $BuildPython -m pip check
    if ($LASTEXITCODE -ne 0) {
        throw "Dependencias inconsistentes na .buildvenv."
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
& $BuildPython -m PyInstaller --clean --noconfirm (Join-Path $ProjectRoot "igreja.spec")
if ($LASTEXITCODE -ne 0) {
    throw "Falha durante o PyInstaller."
}

Write-Host "Validando artefato gerado..."
& $BuildPython (Join-Path $ProjectRoot "scripts\\verify_frozen_build.py") (Join-Path $DistDir "Igreja.exe")
if ($LASTEXITCODE -ne 0) {
    throw "O executavel foi gerado, mas nao contem todos os requireds obrigatorios."
}

Write-Host "Build concluido. Executavel em 'dist\\Igreja.exe'."
