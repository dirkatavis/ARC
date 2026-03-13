param(
    [string]$Version = "1.1.0",
    [switch]$Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-IsccPath {
    $fromPath = Get-Command iscc -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    $envOverride = $env:ISCC_PATH
    if ($envOverride -and (Test-Path $envOverride)) {
        return $envOverride
    }

    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }

    return $null
}

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RepoRoot = (Resolve-Path (Join-Path $ProjectRoot "..")).Path
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    throw "Python virtual environment not found at $VenvPython. Run Launch_ARC.bat once first."
}

$DistRoot = Join-Path $ProjectRoot "dist"
$BuildRoot = Join-Path $ProjectRoot "build"
$ArcDist = Join-Path $DistRoot "ARC"
$InstallerDist = Join-Path $DistRoot "installer"
$InstallerScript = Join-Path $ProjectRoot "installer\arc_setup.iss"
$QuickStartSource = Join-Path $ProjectRoot "installer\ARC_Quick_Start.txt"

if ($Clean) {
    if (Test-Path $DistRoot) { Remove-Item $DistRoot -Recurse -Force }
    if (Test-Path $BuildRoot) { Remove-Item $BuildRoot -Recurse -Force }
}

Write-Host "[ARC] Installing build dependencies..."
& $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements-dev.txt")

Write-Host "[ARC] Building ARC.exe with PyInstaller..."
Push-Location $ProjectRoot
try {
    & $VenvPython -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name ARC `
        --distpath $DistRoot `
        --workpath $BuildRoot `
        --specpath $BuildRoot `
        --collect-submodules customtkinter `
        --collect-data customtkinter `
        main.py
}
finally {
    Pop-Location
}

if (-not (Test-Path (Join-Path $ArcDist "ARC.exe"))) {
    throw "Build failed: ARC.exe was not created."
}

$isccPath = Resolve-IsccPath
if (-not $isccPath) {
    throw "Inno Setup Compiler (ISCC.exe) not found. Install Inno Setup 6, add ISCC.exe to PATH, or set ISCC_PATH env var."
}

Write-Host "[ARC] Compiling setup.exe with Inno Setup..."
& $isccPath /Qp "/DMyAppVersion=$Version" "/DArcDistDir=$ArcDist" $InstallerScript

$SetupPath = Join-Path $InstallerDist "ARC_Setup.exe"
if (-not (Test-Path $SetupPath)) {
    throw "Installer build failed: ARC_Setup.exe was not created."
}

if (-not (Test-Path $QuickStartSource)) {
    throw "Quick start file is missing: $QuickStartSource"
}

Copy-Item $QuickStartSource -Destination (Join-Path $InstallerDist "ARC_Quick_Start.txt") -Force

Write-Host "[ARC] Installer ready: $SetupPath"
Write-Host "[ARC] Quick start guide ready: $(Join-Path $InstallerDist 'ARC_Quick_Start.txt')"
