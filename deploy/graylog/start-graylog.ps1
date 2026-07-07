param(
    [string]$DeployPath = $PSScriptRoot,
    [string]$AdminPassword = "admin"
)

$ErrorActionPreference = "Stop"

function New-RandomSecret {
    $bytes = New-Object byte[] 48
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
        return [Convert]::ToBase64String($bytes)
    }
    finally {
        $rng.Dispose()
    }
}

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$Value)

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
        $hash = $sha.ComputeHash($bytes)
        return -join ($hash | ForEach-Object { $_.ToString("x2") })
    }
    finally {
        $sha.Dispose()
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found. Install Docker Desktop or Docker Engine before starting Graylog."
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker daemon is not reachable. Start Docker Desktop or Docker Engine before starting Graylog."
}

$envPath = Join-Path $DeployPath ".env"
if (-not (Test-Path -LiteralPath $envPath)) {
    $passwordHash = Get-Sha256Hex -Value $AdminPassword
    $passwordSecret = New-RandomSecret
    $opensearchPassword = New-RandomSecret

    @"
GRAYLOG_IMAGE=graylog/graylog:7.1
MONGODB_IMAGE=mongo:6.0.18
OPENSEARCH_IMAGE=opensearchproject/opensearch:2.15.0
GRAYLOG_HTTP_EXTERNAL_URI=http://127.0.0.1:9000/
GRAYLOG_PASSWORD_SECRET=$passwordSecret
GRAYLOG_ROOT_PASSWORD_SHA2=$passwordHash
OPENSEARCH_INITIAL_ADMIN_PASSWORD=$opensearchPassword
"@ | Set-Content -LiteralPath $envPath -Encoding ASCII

    Write-Host "Created local Graylog environment file: $envPath"
    Write-Host "Default local Graylog login: admin / $AdminPassword"
}

$composeFile = Join-Path $DeployPath "docker-compose.yml"
docker compose --env-file $envPath -f $composeFile up -d
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed to start the Graylog stack."
}

Write-Host "Graylog stack requested."
Write-Host "UI: http://127.0.0.1:9000/"
Write-Host "GELF HTTP input URL after creation: http://127.0.0.1:12201/gelf"
Write-Host "Run deploy\graylog\create-gelf-http-input.ps1 after the Graylog API is ready."
