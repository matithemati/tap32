# Buduje dist\Tap32.exe (PyInstaller, jeden plik).
# Użycie (PowerShell, w katalogu app):  .\build_exe.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
$py = ".\.venv\Scripts\python.exe"
& $py -m pip install --upgrade pip | Out-Null
& $py -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) { throw "Instalacja zależności nie powiodła się" }

& $py scripts\make_icon.py
if ($LASTEXITCODE -ne 0) { throw "Nie udało się wygenerować ikony" }

& $py -m PyInstaller tap32.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller zakończył się błędem" }

Write-Host "Gotowe: $PSScriptRoot\dist\Tap32.exe"
