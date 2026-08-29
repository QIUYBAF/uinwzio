$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$VenvPython = Join-Path $PSScriptRoot ".venv-build\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    python -m venv .venv-build
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements-dev.txt
& $VenvPython -m pytest -q
& $VenvPython -m PyInstaller --noconfirm --clean RNGtuber.spec

$Exe = Join-Path $PSScriptRoot "dist\RNGtuber\RNGtuber.exe"
if (-not (Test-Path $Exe)) {
    throw "PyInstaller did not produce RNGtuber.exe"
}

$Diagnostics = Start-Process -FilePath $Exe -ArgumentList "--diagnostics" -PassThru -Wait
if ($Diagnostics.ExitCode -ne 0) {
    throw "Packaged diagnostics failed with exit code $($Diagnostics.ExitCode)"
}

$Smoke = Start-Process -FilePath $Exe -ArgumentList "--demo --smoke-seconds 3" -PassThru -Wait
if ($Smoke.ExitCode -ne 0) {
    throw "Packaged GUI smoke test failed with exit code $($Smoke.ExitCode)"
}

& $VenvPython tools\package_release.py
Write-Host "Release ready: release\RNGtuber_V1_Windows.zip"

