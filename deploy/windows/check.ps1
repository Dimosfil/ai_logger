param(
    [string]$RepoPath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$VenvPath = "",
    [string]$EnvFile = (Join-Path $PSScriptRoot "env.local.ps1"),
    [switch]$SkipGraylog
)

$ErrorActionPreference = "Stop"

if (-not $VenvPath) {
    $VenvPath = Join-Path $RepoPath ".venv"
}

if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Missing env file: $EnvFile. Copy env.example.ps1 to env.local.ps1 and edit it for this machine."
}

. $EnvFile

$scriptsPath = Join-Path $VenvPath "Scripts"
$serverCheck = Join-Path $scriptsPath "ai-logger-server-check.exe"
$clientCheck = Join-Path $scriptsPath "ai-logger-client-check.exe"
$graylogCheck = Join-Path $scriptsPath "ai-logger-graylog-check.exe"

foreach ($command in @($serverCheck, $clientCheck)) {
    if (-not (Test-Path -LiteralPath $command)) {
        throw "Missing command: $command. Run deploy\windows\install.ps1 first."
    }
}

Write-Host "Checking server health..."
& $serverCheck

Write-Host "Checking ingest route..."
& $clientCheck

if (-not $SkipGraylog -and $env:AI_LOGGER_GRAYLOG_GELF_URL) {
    if (-not (Test-Path -LiteralPath $graylogCheck)) {
        throw "Missing command: $graylogCheck. Run deploy\windows\install.ps1 first."
    }
    Write-Host "Checking Graylog GELF HTTP input..."
    & $graylogCheck
}

Write-Host "Windows deployment checks completed."
