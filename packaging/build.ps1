$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    python -m pip install -e ".[dev]"
    if ($LASTEXITCODE -ne 0) { throw "Could not install project build dependencies." }

    python -m ruff check .
    if ($LASTEXITCODE -ne 0) { throw "Ruff checks failed." }

    python -m pytest
    if ($LASTEXITCODE -ne 0) { throw "Pytest failed." }

    python -m PyInstaller --noconfirm --clean packaging\divyaraj.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
    New-Item -ItemType Directory -Force dist\installer | Out-Null

    $compilerCandidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )
    $compiler = $compilerCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $compiler) {
        throw "Inno Setup 6 was not found. Install the free Inno Setup compiler, then rerun this script."
    }

    $versionLine = Select-String -Path pyproject.toml -Pattern '^version = "([^"]+)"'
    if (-not $versionLine) { throw "Could not read the project version from pyproject.toml." }
    $version = [regex]::Match($versionLine.Line, '^version = "([^"]+)"').Groups[1].Value
    & $compiler "/DAppVersion=$version" packaging\installer.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed." }

    Write-Host "Installer created at dist\installer\DivyarajSetup.exe"
}
finally {
    Pop-Location
}
