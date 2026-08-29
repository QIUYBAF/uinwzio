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
& $VenvPython -m PyInstaller --noconfirm --clean RNGtuber.spec

$Exe = Join-Path $PSScriptRoot "dist\RNGtuber\RNGtuber.exe"
if (-not (Test-Path $Exe)) {
    throw "PyInstaller did not produce RNGtuber.exe"
}

function Invoke-CheckedProcess {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [Parameter(Mandatory=$true)][string]$Arguments,
        [Parameter(Mandatory=$true)][int]$TimeoutMs,
        [Parameter(Mandatory=$true)][string]$Label
    )

    $Process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -PassThru
    if (-not $Process.WaitForExit($TimeoutMs)) {
        try { Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue } catch {}
        throw "$Label timed out after $([math]::Round($TimeoutMs / 1000, 1)) seconds"
    }
    $Process.Refresh()
    if ($Process.ExitCode -ne 0) {
        throw "$Label failed with exit code $($Process.ExitCode)"
    }
}

# Cold-starting a Qt onedir app on a fresh Windows runner can take noticeably
# longer than on a user's machine. Keep explicit bounds so regressions fail in
# under a minute instead of consuming the whole workflow timeout.
Invoke-CheckedProcess -FilePath $Exe -Arguments "--diagnostics" -TimeoutMs 45000 -Label "Packaged diagnostics"
Invoke-CheckedProcess -FilePath $Exe -Arguments "--demo --smoke-seconds 3" -TimeoutMs 30000 -Label "Packaged GUI smoke test"

& $VenvPython tools\package_release.py
Write-Host "Release ready: release\RNGtuber_V1_Windows.zip"
