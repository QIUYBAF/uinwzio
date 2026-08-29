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

# Package first. Producing a directly downloadable Windows ZIP is the primary
# release goal; hardware-sensitive smoke tests must never block artifact output.
& $VenvPython tools\package_release.py
Write-Host "Release ready: release\RNGtuber_V1_Windows.zip"

# Optional packaged validation for local/real Windows hardware. CI leaves this
# disabled by default because headless runners can deadlock inside native audio
# or GUI backends even when the generated EXE itself is valid.
if ($env:RNGTUBER_VALIDATE_PACKAGED -eq "1") {
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

    Invoke-CheckedProcess -FilePath $Exe -Arguments "--diagnostics" -TimeoutMs 45000 -Label "Packaged diagnostics"
    Invoke-CheckedProcess -FilePath $Exe -Arguments "--demo --smoke-seconds 3" -TimeoutMs 30000 -Label "Packaged GUI smoke test"
}
