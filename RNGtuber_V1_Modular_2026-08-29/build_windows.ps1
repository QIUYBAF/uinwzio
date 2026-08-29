$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$VenvPython = Join-Path $PSScriptRoot ".venv-build\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    python -m venv .venv-build
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements-dev.txt
& $VenvPython tools\render_visual_qa.py
& $VenvPython tools\render_motion_preview.py
& $VenvPython -m pytest -q
& $VenvPython -m compileall -q rngtuber
& $VenvPython -m PyInstaller --noconfirm --clean RNGtuber.spec

$Exe = Join-Path $PSScriptRoot "dist\RNGtuber\RNGtuber.exe"
if (-not (Test-Path $Exe)) {
    throw "PyInstaller did not produce RNGtuber.exe"
}

# Package first so a release archive always exists before optional validation.
& $VenvPython tools\package_release.py
Write-Host "Release ready: release\RNGtuber_V1_Windows.zip"

# Fast, hardware-safe packaged GUI smoke test. Demo mode avoids real microphone
# and controller probing, while still importing window -> renderer and creating
# the Qt application. This specifically catches missing bundled modules such as
# rngtuber.renderer without reintroducing the old headless diagnostics hang.
if ($env:RNGTUBER_VALIDATE_PACKAGED -eq "1") {
    $Process = Start-Process -FilePath $Exe -ArgumentList "--demo --smoke-seconds 1" -PassThru
    if (-not $Process.WaitForExit(12000)) {
        try { Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue } catch {}
        throw "Packaged GUI smoke test timed out after 12 seconds"
    }
    $Process.Refresh()
    if ($Process.ExitCode -ne 0) {
        throw "Packaged GUI smoke test failed with exit code $($Process.ExitCode)"
    }
    Write-Host "Packaged GUI smoke test passed"
}
