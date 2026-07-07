param(
    [string]$GraylogUrl = "http://127.0.0.1:9000",
    [string]$Username = "admin",
    [string]$Password = "admin",
    [int]$Port = 12201,
    [string]$Title = "ai_logger GELF HTTP"
)

$ErrorActionPreference = "Stop"

function New-BasicAuthHeader {
    param(
        [Parameter(Mandatory = $true)][string]$User,
        [Parameter(Mandatory = $true)][string]$Pass
    )

    $bytes = [System.Text.Encoding]::ASCII.GetBytes("${User}:${Pass}")
    return "Basic " + [Convert]::ToBase64String($bytes)
}

$headers = @{
    Authorization = New-BasicAuthHeader -User $Username -Pass $Password
    "X-Requested-By" = "ai_logger"
    Accept = "application/json"
}

Write-Host "Checking Graylog API at $GraylogUrl..."
Invoke-RestMethod -Uri "$GraylogUrl/api/system/lbstatus" -Headers $headers -TimeoutSec 10 | Out-Null

$existing = Invoke-RestMethod -Uri "$GraylogUrl/api/system/inputs" -Headers $headers -TimeoutSec 10
$match = @($existing.inputs | Where-Object { $_.title -eq $Title }) | Select-Object -First 1
if ($match) {
    Write-Host "Graylog input already exists: $Title"
    Write-Host "GELF HTTP URL: http://127.0.0.1:$Port/gelf"
    exit 0
}

$body = @{
    title = $Title
    type = "org.graylog2.inputs.gelf.http.GELFHttpInput"
    global = $true
    configuration = @{
        bind_address = "0.0.0.0"
        port = $Port
        recv_buffer_size = 1048576
        number_worker_threads = 2
        tls_enable = $false
        tls_cert_file = ""
        tls_key_file = ""
        tls_key_password = ""
        max_chunk_size = 65536
        decompress_size_limit = 8388608
    }
}

$json = $body | ConvertTo-Json -Depth 8
Invoke-RestMethod `
    -Uri "$GraylogUrl/api/system/inputs" `
    -Headers $headers `
    -ContentType "application/json" `
    -Method Post `
    -Body $json `
    -TimeoutSec 20 | Out-Null

Write-Host "Created Graylog input: $Title"
Write-Host "GELF HTTP URL: http://127.0.0.1:$Port/gelf"

