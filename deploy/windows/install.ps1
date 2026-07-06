param(
    [string]$RepoPath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$VenvPath = "",
    [string]$PythonCommand = "python"
)

$ErrorActionPreference = "Stop"

if (-not $VenvPath) {
    $VenvPath = Join-Path $RepoPath ".venv"
}

if (-not (Test-Path -LiteralPath (Join-Path $RepoPath "pyproject.toml"))) {
    throw "RepoPath does not look like the ai_logger repository: $RepoPath"
}

Write-Host "Using repository: $RepoPath"
Write-Host "Using virtual environment: $VenvPath"

if (-not (Test-Path -LiteralPath $VenvPath)) {
    & $PythonCommand -m venv $VenvPath
}

$pythonExe = Join-Path $VenvPath "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Virtual environment Python was not created: $pythonExe"
}

& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -e $RepoPath

Write-Host "ai_logger installed. Next:"
Write-Host "  Copy deploy\windows\env.example.ps1 to deploy\windows\env.local.ps1"
Write-Host "  Edit env.local.ps1 for this machine"
Write-Host "  Run deploy\windows\start-server.ps1"
