param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(0, 36500)]
    [int]$Days,

    [string]$DbPath = "",

    [string]$SqliteExe = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Exit-Blocked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Reason,
        [Parameter(Mandatory = $true)]
        [string]$NextStep
    )

    Write-Host "BLOCKED: $Reason" -ForegroundColor Yellow
    Write-Host "Next step: $NextStep"
    exit 2
}

function Resolve-SqliteExe {
    param([string]$RequestedPath)

    if (-not [string]::IsNullOrWhiteSpace($RequestedPath) -and (Test-Path $RequestedPath)) {
        return (Resolve-Path $RequestedPath).Path
    }

    $fromPath = Get-Command sqlite3 -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    $candidates = @()
    if (-not [string]::IsNullOrWhiteSpace($PSScriptRoot)) {
        $candidates += (Join-Path $PSScriptRoot "sqlite3.exe")

        $parent = Split-Path $PSScriptRoot -Parent
        if (-not [string]::IsNullOrWhiteSpace($parent)) {
            $candidates += (Join-Path $parent "tools\sqlite3.exe")
        }
    }

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }

    return $null
}

if ([string]::IsNullOrWhiteSpace($DbPath)) {
    if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        $DbPath = Join-Path $env:LOCALAPPDATA "ARC\data\arc_data.db"
    }
    else {
        $localAppData = [Environment]::GetFolderPath("LocalApplicationData")
        $DbPath = Join-Path $localAppData "ARC\data\arc_data.db"
    }
}

if (-not (Test-Path $DbPath)) {
    Exit-Blocked `
        -Reason "Database not found at '$DbPath'." `
        -NextStep "Launch ARC once to complete first-run setup, then run this script again."
}

$sqlitePath = Resolve-SqliteExe -RequestedPath $SqliteExe
if (-not $sqlitePath) {
    Exit-Blocked `
        -Reason "sqlite3.exe not found." `
        -NextStep "Install SQLite CLI and add it to PATH, or rerun with -SqliteExe <full path>."
}

$installDate = (Get-Date).Date.AddDays(-$Days).ToString("yyyy-MM-dd")

$checkSql = "SELECT id FROM sys_entitlement WHERE id = 1;"
$checkResult = & $sqlitePath $DbPath $checkSql
if ($LASTEXITCODE -ne 0) {
    Exit-Blocked `
        -Reason "Could not query sys_entitlement (database not initialized, inaccessible, or locked)." `
        -NextStep "Launch ARC once, close ARC, and rerun this script."
}
if (-not $checkResult) {
    Exit-Blocked `
        -Reason "sys_entitlement row (id = 1) was not found." `
        -NextStep "Launch ARC once to initialize entitlement metadata, then rerun this script."
}

$updateSql = "UPDATE sys_entitlement SET install_date = '$installDate' WHERE id = 1;"
& $sqlitePath $DbPath $updateSql
if ($LASTEXITCODE -ne 0) {
    Exit-Blocked `
        -Reason "Failed to update install_date (database may be locked)." `
        -NextStep "Close ARC and any DB viewer tools, then rerun this script."
}

$trialDays = 15
$daysRemaining = [Math]::Max(0, $trialDays - $Days)
if ($Days -gt $trialDays) {
    $state = "EXPIRED"
}
else {
    $state = "TRIAL ($daysRemaining day$(if ($daysRemaining -ne 1) { 's' } else { '' }) remaining)"
}

Write-Host "Database            : $DbPath"
Write-Host "sqlite3             : $sqlitePath"
Write-Host "install_date set to : $installDate ($Days day$(if ($Days -ne 1) { 's' } else { '' }) ago)"
Write-Host "Effective state     : $state"
Write-Host "Relaunch ARC to verify UI behavior."
