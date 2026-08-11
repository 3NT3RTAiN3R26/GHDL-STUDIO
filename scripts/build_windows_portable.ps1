<#
.SYNOPSIS
  Build a Windows portable GHDL Studio folder (PyInstaller onedir) and zip it.

.DESCRIPTION
  Run on Windows (local or GitHub Actions windows-latest).
  Output:
    dist/GHDL-Studio/GHDL-Studio.exe
    dist/GHDL-Studio-windows-portable-<version>.zip

.PARAMETER Version
  Override version string used in the zip name. Default: read from pyproject.toml.
#>
[CmdletBinding()]
param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

function Get-ProjectVersion {
    $toml = Get-Content -Path (Join-Path $Root "pyproject.toml") -Raw
    if ($toml -match 'version\s*=\s*"([^"]+)"') {
        return $Matches[1]
    }
    throw "Could not read version from pyproject.toml"
}

if (-not $Version) {
    $Version = Get-ProjectVersion
}

Write-Host "Building GHDL Studio Windows portable v$Version"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
python -m pip install "pyinstaller>=6.3,<7"

$spec = Join-Path $Root "packaging\ghdl_studio_windows.spec"
if (-not (Test-Path $spec)) {
    throw "Missing spec file: $spec"
}

python -m PyInstaller --noconfirm --clean $spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$distDir = Join-Path $Root "dist\GHDL-Studio"
$exe = Join-Path $distDir "GHDL-Studio.exe"
if (-not (Test-Path $exe)) {
    throw "Expected executable not found: $exe"
}

# Ship examples next to the exe so File → Open example works without a repo checkout.
$examplesSrc = Join-Path $Root "examples"
$examplesDst = Join-Path $distDir "examples"
if (Test-Path $examplesSrc) {
    if (Test-Path $examplesDst) {
        Remove-Item -Recurse -Force $examplesDst
    }
    Copy-Item -Recurse -Force $examplesSrc $examplesDst
}

# Write a VERSION.txt next to the exe (handy for support; About still uses __version__).
Set-Content -Path (Join-Path $distDir "VERSION.txt") -Value $Version -NoNewline

# Smoke: --version should print even for a windowed build when stdout is redirected.
$versionOut = & $exe --version 2>&1 | Out-String
Write-Host "Portable --version output:`n$versionOut"
if ($versionOut -notmatch [regex]::Escape($Version)) {
    Write-Warning "Direct --version capture failed; retrying via ProcessStartInfo redirection."
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $exe
    $psi.Arguments = "--version"
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $proc = [System.Diagnostics.Process]::Start($psi)
    $stdout = $proc.StandardOutput.ReadToEnd()
    $stderr = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit(60000) | Out-Null
    $versionOut = "$stdout`n$stderr"
    Write-Host "Redirected --version output:`n$versionOut"
}
if ($versionOut -notmatch [regex]::Escape($Version)) {
    throw "Portable --version did not contain expected version '$Version'. Got:`n$versionOut"
}

$zipName = "GHDL-Studio-windows-portable-$Version.zip"
$zipPath = Join-Path $Root "dist\$zipName"
if (Test-Path $zipPath) {
    Remove-Item -Force $zipPath
}

Compress-Archive -Path $distDir -DestinationPath $zipPath -Force
Write-Host "Created $zipPath"
Write-Output $zipPath
