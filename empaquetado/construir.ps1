# Construye el ejecutable unico de NARSIL Pass en Windows, con el escudo como icono:
#   dist\narsil-pass-windows-x86_64.exe  (Windows x64) · dist\narsil-pass-windows-arm64.exe (ARM64)
#   powershell -NoProfile -ExecutionPolicy Bypass -File empaquetado\construir.ps1
# Requiere Python 3.11+ en el PATH y la interfaz compilada en ui\dist\index.html.
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $raiz
if (-not (Test-Path "ui\dist\index.html")) { throw "Falta ui\dist\index.html: cd ui; npm ci; npm run build" }
$venv = ".venv-build"
if (-not (Test-Path "$venv\Scripts\python.exe")) { python -m venv $venv }
$py = "$venv\Scripts\python.exe"
& $py -m pip install --disable-pip-version-check --quiet --upgrade pip
& $py -m pip install --disable-pip-version-check --quiet -r requirements.txt -r empaquetado\requirements-build.txt
$arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "x86_64" }
$nombre = "narsil-pass-windows-$arch"
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
& $py -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name $nombre --icon "$raiz\empaquetado\narsil.ico" `
    --distpath "dist" --workpath "build" --specpath "build" `
    --paths "$raiz" `
    --add-data "$raiz\ui\dist\index.html;ui\dist" `
    --add-data "$raiz\nucleo\datos;nucleo\datos" `
    --add-data "$raiz\empaquetado\narsil.ico;empaquetado" `
    --collect-submodules app --collect-submodules nucleo `
    --collect-all webview --collect-all argon2 `
    --exclude-module numpy --exclude-module tkinter --exclude-module PIL --exclude-module matplotlib `
    --collect-all clr_loader --collect-all pythonnet `
    "$raiz\narsil_pass.py"
& "dist\$nombre.exe" --autoprueba | Out-Host
$exe = Get-Item "dist\$nombre.exe"
Write-Host ("CONSTRUIDO " + $exe.FullName + " (" + [math]::Round($exe.Length / 1MB, 1) + " MB)")
