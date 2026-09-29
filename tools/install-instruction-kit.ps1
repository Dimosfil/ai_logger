[CmdletBinding()]
param(
    [string]$Source = "https://github.com/Dimosfil/general-instructions.git",
    [string]$TargetPath = (Get-Location).Path,
    [string]$SourceRoot = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$CanonicalSource = "https://github.com/Dimosfil/general-instructions.git"
$TemporaryCheckout = $null

function Resolve-GiSource {
    param([Parameter(Mandatory = $true)][string]$Value)

    $candidate = $Value.Trim()
    $markdownMatch = [regex]::Match(
        $candidate,
        '\[[^\]]+\]\((?<href>https://github\.com/Dimosfil/general-instructions(?:\.git)?(?:/)?(?:[?#][^)]*)?)\)',
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )
    if ($markdownMatch.Success) {
        $candidate = $markdownMatch.Groups['href'].Value
    }

    if ($candidate -match '^(?:https://github\.com/)?Dimosfil/general-instructions(?:\.git)?/?$') {
        return [pscustomobject]@{
            Kind = "git"
            Canonical = $CanonicalSource
            LocalPath = ""
        }
    }

    if (Test-Path -LiteralPath $candidate -PathType Container) {
        return [pscustomobject]@{
            Kind = "local"
            Canonical = $CanonicalSource
            LocalPath = (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "Unsupported GI source '$Value'. Use the canonical GitHub repository, its Markdown link, the short repo form, or a local checkout."
}

function Assert-SourceRoot {
    param([Parameter(Mandatory = $true)][string]$Path)

    $required = @(
        "BOOTSTRAP.md",
        "COMMANDS.md",
        "config/gi-command-routes.json",
        "config/gi-context-budgets.json",
        "tools/get-gi-context.ps1",
        "tools/resolve-gi-command.ps1",
        "patterns/GI_COMMAND_CONTRACTS.md",
        "VERSION.md",
        "templates/AGENTS.template.md",
        "templates/instruction-kit.template.json",
        "patterns/SHARED_INSTRUCTIONS_BOOTSTRAP.md"
    )
    foreach ($relativePath in $required) {
        $fullPath = Join-Path $Path $relativePath
        if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
            throw "The GI source checkout is incomplete: missing '$relativePath' under '$Path'."
        }
    }
}

function Ensure-Directory {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        [void](New-Item -ItemType Directory -Path $Path -Force)
    }
}

function Copy-MissingFile {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][System.Collections.Generic.List[string]]$Created,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][System.Collections.Generic.List[string]]$Preserved
    )

    $destinationDirectory = Split-Path -Parent $DestinationPath
    Ensure-Directory -Path $destinationDirectory
    if (Test-Path -LiteralPath $DestinationPath -PathType Leaf) {
        $Preserved.Add($DestinationPath)
        return
    }

    Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath
    $Created.Add($DestinationPath)
}

function Merge-GitIgnoreRules {
    param(
        [Parameter(Mandatory = $true)][string]$TemplatePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    $utf8 = [System.Text.UTF8Encoding]::new($false)
    $templateLines = [System.IO.File]::ReadAllLines($TemplatePath, $utf8)
    $existingLines = if (Test-Path -LiteralPath $DestinationPath -PathType Leaf) {
        [System.IO.File]::ReadAllLines($DestinationPath, $utf8)
    } else {
        @()
    }

    $result = [System.Collections.Generic.List[string]]::new()
    foreach ($line in $existingLines) {
        $result.Add($line)
    }
    $missingLines = @($templateLines | Where-Object { $_ -ne "" -and -not ($result -contains $_) })
    if ($missingLines.Count -eq 0) {
        return
    }
    if ($result.Count -gt 0 -and $result[$result.Count - 1] -ne "") {
        $result.Add("")
    }
    foreach ($line in $missingLines) {
        $result.Add($line)
    }

    [System.IO.File]::WriteAllLines($DestinationPath, $result, $utf8)
}

try {
    $sourceDescriptor = Resolve-GiSource -Value $Source
    $resolvedTarget = (Resolve-Path -LiteralPath $TargetPath).Path

    if ($SourceRoot) {
        $resolvedSourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
    } elseif ($sourceDescriptor.Kind -eq "local") {
        $resolvedSourceRoot = $sourceDescriptor.LocalPath
    } else {
        $TemporaryCheckout = Join-Path ([System.IO.Path]::GetTempPath()) ("gi-bootstrap-" + [guid]::NewGuid().ToString("N"))
        & git clone --depth 1 -- $sourceDescriptor.Canonical $TemporaryCheckout
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to clone the GI source repository."
        }
        $resolvedSourceRoot = (Resolve-Path -LiteralPath $TemporaryCheckout).Path
    }

    Assert-SourceRoot -Path $resolvedSourceRoot
    if ($resolvedSourceRoot.TrimEnd('\', '/') -ieq $resolvedTarget.TrimEnd('\', '/')) {
        throw "The source checkout and target project are the same directory. Use GI start/restore for the general-instructions repository itself."
    }

    $created = [System.Collections.Generic.List[string]]::new()
    $preserved = [System.Collections.Generic.List[string]]::new()
    $mappings = @(
        @{ Source = "BOOTSTRAP.md"; Target = "BOOTSTRAP.md" },
        @{ Source = "templates/AGENTS.template.md"; Target = "AGENTS.md" },
        @{ Source = "COMMANDS.md"; Target = "COMMANDS.md" },
        @{ Source = "config/gi-command-routes.json"; Target = "config/gi-command-routes.json" },
        @{ Source = "config/gi-context-budgets.json"; Target = "config/gi-context-budgets.json" },
        @{ Source = "tools/get-gi-context.ps1"; Target = "tools/get-gi-context.ps1" },
        @{ Source = "tools/resolve-gi-command.ps1"; Target = "tools/resolve-gi-command.ps1" },
        @{ Source = "templates/AGENT_WORKING_AGREEMENTS.template.md"; Target = "tools/AGENT_WORKING_AGREEMENTS.md" },
        @{ Source = "templates/AGENT_RUNBOOK.template.md"; Target = "tools/AGENT_RUNBOOK.md" },
        @{ Source = "templates/agent-start.template.ps1"; Target = "tools/agent-start.ps1" },
        @{ Source = "templates/select-project-language.template.ps1"; Target = "tools/select-project-language.ps1" },
        @{ Source = "templates/select-git-commit-languages.template.ps1"; Target = "tools/select-git-commit-languages.ps1" },
        @{ Source = "templates/select-system-language.template.ps1"; Target = "tools/select-system-language.ps1" },
        @{ Source = "templates/check-instruction-kit-updates.template.ps1"; Target = "tools/check-instruction-kit-updates.ps1" },
        @{ Source = "templates/project-memory-README.template.md"; Target = "tools/project-memory/README.md" },
        @{ Source = "templates/ARCHITECTURE_MIGRATIONS.template.md"; Target = "tools/project-memory/architecture-migrations.md" },
        @{ Source = "templates/STUDY_PLAN.template.md"; Target = "tools/project-memory/STUDY_PLAN.md" },
        @{ Source = "templates/pending-tasks.template.md"; Target = "tools/project-memory/pending-tasks.md" },
        @{ Source = "templates/git-preferences.template.json"; Target = "tools/project-memory/git-preferences.json" },
        @{ Source = "templates/system-preferences.template.json"; Target = "tools/project-memory/system-preferences.json" },
        @{ Source = "templates/rag-system.template.json"; Target = "tools/project-memory/rag-system.json" },
        @{ Source = "tools/project-memory/code_intelligence.py"; Target = "tools/project-memory/code_intelligence.py" },
        @{ Source = "templates/TECHNOLOGY_STACK.template.md"; Target = "tools/project-memory/specs/technology-stack.md" },
        @{ Source = "templates/SYSTEM_MAP.template.md"; Target = "templates/SYSTEM_MAP.template.md" },
        @{ Source = "templates/MODULE_PASSPORT.template.md"; Target = "templates/MODULE_PASSPORT.template.md" },
        @{ Source = "templates/MODULE_CONTRACT.template.md"; Target = "templates/MODULE_CONTRACT.template.md" }
    )

    foreach ($mapping in $mappings) {
        Copy-MissingFile `
            -SourcePath (Join-Path $resolvedSourceRoot $mapping.Source) `
            -DestinationPath (Join-Path $resolvedTarget $mapping.Target) `
            -Created $created `
            -Preserved $preserved
    }

    $runtimeSource = Join-Path $resolvedSourceRoot "patterns/AGENTS_RUNTIME"
    foreach ($runtimeFile in Get-ChildItem -LiteralPath $runtimeSource -File -Filter "*.md") {
        Copy-MissingFile `
            -SourcePath $runtimeFile.FullName `
            -DestinationPath (Join-Path $resolvedTarget ("patterns/AGENTS_RUNTIME/" + $runtimeFile.Name)) `
            -Created $created `
            -Preserved $preserved
    }

    $patternFiles = @(
        "AGENT_ROLE_OFFICE.md",
        "API_KEY_SECRET_SAFETY.md",
        "ARCHITECTURE_AND_CODE_QUALITY.md",
        "MODULAR_SERVICE_ENGINEERING.md",
        "COHERENT_BATCH_VERIFICATION.md",
        "CODE_INTELLIGENCE_ADAPTERS.md",
        "CONFIGURATION_BOUNDARIES.md",
        "DEVELOPMENT_TOOL_PRODUCT_BOUNDARIES.md",
        "EXTERNAL_DOCUMENTATION_RETRIEVAL.md",
        "GI_COMMAND_CONTRACTS.md",
        "PROJECT_DOCUMENTATION_LAYERS.md",
        "PROJECT_DEV_PROD_SERVICES.md",
        "QUERY_PROMPT_NORMALIZATION_BOUNDARIES.md",
        "STARTUP_PRODUCT_ENGINEERING.md",
        "TECHNOLOGY_STACK_INVENTORY.md"
    )
    foreach ($patternFile in $patternFiles) {
        Copy-MissingFile `
            -SourcePath (Join-Path $resolvedSourceRoot ("patterns/" + $patternFile)) `
            -DestinationPath (Join-Path $resolvedTarget ("patterns/" + $patternFile)) `
            -Created $created `
            -Preserved $preserved
    }

    Ensure-Directory -Path (Join-Path $resolvedTarget "tools/summary")
    Merge-GitIgnoreRules `
        -TemplatePath (Join-Path $resolvedSourceRoot "templates/gitignore-agent-memory.template") `
        -DestinationPath (Join-Path $resolvedTarget ".gitignore")

    $instructionKitTarget = Join-Path $resolvedTarget "tools/project-memory/instruction-kit.json"
    if (Test-Path -LiteralPath $instructionKitTarget -PathType Leaf) {
        $preserved.Add($instructionKitTarget)
    } else {
        $instructionKitTemplate = Join-Path $resolvedSourceRoot "templates/instruction-kit.template.json"
        $metadata = Get-Content -Raw -LiteralPath $instructionKitTemplate | ConvertFrom-Json
        $metadata.installed_at = [DateTimeOffset]::UtcNow.ToString("o")
        $metadata.source = $CanonicalSource
        $metadata.update_check.source_repo = $CanonicalSource
        if ($sourceDescriptor.Kind -eq "local") {
            $metadata.update_check.source_cache_path = $resolvedSourceRoot
            $metadata.update_check.shared_library_path = $resolvedSourceRoot
        } else {
            $metadata.update_check.source_cache_path = ""
            $metadata.update_check.shared_library_path = ""
        }
        $json = $metadata | ConvertTo-Json -Depth 100
        $utf8 = [System.Text.UTF8Encoding]::new($false)
        [System.IO.File]::WriteAllText($instructionKitTarget, $json + [Environment]::NewLine, $utf8)
        $created.Add($instructionKitTarget)
    }

    [pscustomobject]@{
        source_repo = $CanonicalSource
        source_checkout = $resolvedSourceRoot
        target_project = $resolvedTarget
        created_count = $created.Count
        preserved_count = $preserved.Count
        created = $created
        preserved = $preserved
        next_step = "Inspect TODO placeholders, merge any preserved instruction files, then ask about task-manager plan sync."
    }
} finally {
    if ($TemporaryCheckout -and (Test-Path -LiteralPath $TemporaryCheckout -PathType Container)) {
        $resolvedTemporaryCheckout = (Resolve-Path -LiteralPath $TemporaryCheckout).Path
        $resolvedTempRoot = (Resolve-Path -LiteralPath ([System.IO.Path]::GetTempPath())).Path
        if (-not $resolvedTemporaryCheckout.StartsWith($resolvedTempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove temporary checkout outside the system temp directory: $resolvedTemporaryCheckout"
        }
        Remove-Item -LiteralPath $resolvedTemporaryCheckout -Recurse -Force
    }
}
