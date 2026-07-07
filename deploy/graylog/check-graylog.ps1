param(
    [string]$DeployPath = $PSScriptRoot,
    [string]$GraylogUrl = "http://127.0.0.1:9000",
    [string]$GelfUrl = "http://127.0.0.1:12201/gelf"
)

$ErrorActionPreference = "Stop"

$envPath = Join-Path $DeployPath ".env"
if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Missing Graylog .env file: $envPath. Run deploy\graylog\start-graylog.ps1 first."
}

Write-Host "Docker Compose services:"
docker compose --env-file $envPath -f (Join-Path $DeployPath "docker-compose.yml") ps

Write-Host "Checking Graylog API..."
$api = Invoke-RestMethod -Uri "$GraylogUrl/api/system/lbstatus" -TimeoutSec 10
$api | ConvertTo-Json -Depth 5

Write-Host "Checking GELF HTTP input with ai_logger payload..."
$root = Resolve-Path -LiteralPath (Join-Path $DeployPath "..\..")
$graylogCheck = Join-Path $root ".venv\Scripts\ai-logger-graylog-check.exe"
if (Test-Path -LiteralPath $graylogCheck) {
    & $graylogCheck --url $GelfUrl --host "ai-logger-local"
}
else {
    Write-Host "ai-logger-graylog-check.exe not found. Install ai_logger first or run:"
    Write-Host "  python -m ai_logger.graylog_check --url $GelfUrl --host ai-logger-local"
}

