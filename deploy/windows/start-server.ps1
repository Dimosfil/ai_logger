param(
    [string]$RepoPath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$VenvPath = "",
    [string]$EnvFile = (Join-Path $PSScriptRoot "env.local.ps1"),
    [switch]$Background,
    [switch]$AllowExampleConfig
)

$ErrorActionPreference = "Stop"

if (-not $VenvPath) {
    $VenvPath = Join-Path $RepoPath ".venv"
}

if (-not (Test-Path -LiteralPath $EnvFile)) {
    if ($AllowExampleConfig) {
        $EnvFile = Join-Path $PSScriptRoot "env.example.ps1"
    } else {
        throw "Missing env file: $EnvFile. Copy env.example.ps1 to env.local.ps1 and edit it for this machine."
    }
}

. $EnvFile

$serverExe = Join-Path $VenvPath "Scripts\ai-logger-server.exe"
if (-not (Test-Path -LiteralPath $serverExe)) {
    throw "ai-logger-server was not found at $serverExe. Run deploy\windows\install.ps1 first."
}

$workDir = $RepoPath
New-Item -ItemType Directory -Force -Path (Join-Path $workDir "logs") | Out-Null

if ($Background) {
    $process = Start-Process -WindowStyle Hidden -FilePath $serverExe -WorkingDirectory $workDir -PassThru
    $pidPath = Join-Path $workDir "logs\ai-logger-server.pid"
    Set-Content -LiteralPath $pidPath -Value $process.Id -Encoding ASCII
    Write-Host "ai_logger server started in background. PID: $($process.Id)"
    Write-Host "PID file: $pidPath"
} else {
    Write-Host "Starting ai_logger server in foreground. Press Ctrl+C to stop."
    & $serverExe
}
