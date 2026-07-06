param(
    [string]$RepoPath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
)

$ErrorActionPreference = "Stop"

$pidPath = Join-Path $RepoPath "logs\ai-logger-server.pid"
if (-not (Test-Path -LiteralPath $pidPath)) {
    throw "PID file not found: $pidPath"
}

$serverPid = [int](Get-Content -LiteralPath $pidPath -Raw)
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $serverPid"

if (-not $process) {
    Remove-Item -LiteralPath $pidPath -Force
    Write-Host "No running process found for PID $serverPid. Removed stale PID file."
    exit 0
}

if ($process.CommandLine -notlike "*ai-logger-server*") {
    throw "PID $serverPid does not look like ai-logger-server. Command line: $($process.CommandLine)"
}

Stop-Process -Id $serverPid -ErrorAction Stop
Remove-Item -LiteralPath $pidPath -Force
Write-Host "Stopped ai_logger server. PID: $serverPid"
