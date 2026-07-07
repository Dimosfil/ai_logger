param(
    [string]$DeployPath = $PSScriptRoot
)

$ErrorActionPreference = "Stop"

$envPath = Join-Path $DeployPath ".env"
if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Missing Graylog .env file: $envPath"
}

docker compose --env-file $envPath -f (Join-Path $DeployPath "docker-compose.yml") down

