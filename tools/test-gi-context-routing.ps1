[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$manifestPath = Join-Path $repoRoot "config/gi-command-routes.json"
$budgetPath = Join-Path $repoRoot "config/gi-context-budgets.json"
$resolverPath = Join-Path $repoRoot "tools/resolve-gi-command.ps1"
$builderPath = Join-Path $repoRoot "tools/get-gi-context.ps1"
$updaterTemplate = Join-Path $repoRoot "templates/check-instruction-kit-updates.template.ps1"
$testRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("gi-context-routing-" + [guid]::NewGuid().ToString("N"))
$compatibilityModules = @(
    "patterns/AGENTS_RUNTIME/07-startup-and-scope.md",
    "patterns/AGENTS_RUNTIME/08-config-service-and-task-manager.md",
    "patterns/AGENTS_RUNTIME/09-project-operation-commands.md"
)

function Assert-Contains {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$Expected,
        [Parameter(Mandatory = $true)][string]$Failure
    )
    if (-not $Text.Contains($Expected)) { throw $Failure }
}

function Assert-FileBudget {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][long]$Maximum
    )
    $length = (Get-Item -LiteralPath (Join-Path $repoRoot $RelativePath)).Length
    if ($length -gt $Maximum) {
        throw "$RelativePath exceeded its context budget: $length > $Maximum bytes."
    }
}

function New-UpdateFixture {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$MetadataJson,
        [switch]$WithoutMigrations
    )
    $source = Join-Path $testRoot "$Name-source"
    $project = Join-Path $testRoot "$Name-project"
    [void](New-Item -ItemType Directory -Path $source -Force)
    [void](New-Item -ItemType Directory -Path (Join-Path $project "tools/project-memory") -Force)
    [System.IO.File]::WriteAllText(
        (Join-Path $source "VERSION.md"),
        "Current accepted version: ``2026.09.22.2``",
        [System.Text.UTF8Encoding]::new($false)
    )
    if (-not $WithoutMigrations) {
        [void](New-Item -ItemType Directory -Path (Join-Path $source "migrations") -Force)
        foreach ($id in @("2026.09.22.1__already", "2026.09.22.2__pending")) {
            [System.IO.File]::WriteAllText(
                (Join-Path $source "migrations/$id.md"),
                "# $id",
                [System.Text.UTF8Encoding]::new($false)
            )
        }
    }
    [System.IO.File]::WriteAllText(
        (Join-Path $project "tools/project-memory/instruction-kit.json"),
        $MetadataJson,
        [System.Text.UTF8Encoding]::new($false)
    )
    return [pscustomobject]@{ Source = $source; Project = $project }
}

try {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $budgets = Get-Content -LiteralPath $budgetPath -Raw | ConvertFrom-Json
    $aliases = @{}
    foreach ($route in $manifest.routes) {
        if (-not $route.id -or -not $route.contract -or @($route.aliases).Count -eq 0) {
            throw "Route is missing id, contract, or aliases."
        }
        foreach ($aliasValue in $route.aliases) {
            $alias = ([string]$aliasValue).Trim().ToLowerInvariant()
            if ($aliases.ContainsKey($alias) -and $aliases[$alias] -ne $route.id) {
                throw "Alias '$alias' is assigned to both '$($aliases[$alias])' and '$($route.id)'."
            }
            $aliases[$alias] = [string]$route.id
        }
        $routeAliases = @($route.aliases | ForEach-Object { ([string]$_).Trim().ToLowerInvariant() })
        foreach ($alias in $routeAliases) {
            if ($alias -match '^gi (?<tail>.*[А-Яа-яЁё].*)$') {
                $cyrillicPrefixAlias = "ги $($Matches.tail)"
                if ($routeAliases -notcontains $cyrillicPrefixAlias) {
                    throw "Route '$($route.id)' is missing Cyrillic-prefix alias '$cyrillicPrefixAlias' for '$alias'."
                }
            }
        }
        foreach ($relativePathValue in $route.context_files) {
            $relativePath = [string]$relativePathValue
            if ($compatibilityModules -contains $relativePath) {
                throw "Route '$($route.id)' loads compatibility-only module '$relativePath'."
            }
            if (-not (Test-Path -LiteralPath (Join-Path $repoRoot $relativePath) -PathType Leaf)) {
                throw "Route '$($route.id)' references missing context file '$relativePath'."
            }
        }

        $packet = (& $resolverPath -CommandText ([string]$route.aliases[0]) | Out-String)
        $maximum = [int]$budgets.route_packet_default_max_chars
        $override = $budgets.route_packet_overrides.PSObject.Properties[[string]$route.id]
        if ($override) { $maximum = [int]$override.Value }
        if ($packet.Length -gt $maximum) {
            throw "Route '$($route.id)' exceeded its packet budget: $($packet.Length) > $maximum chars."
        }
    }

    $routeCases = @(
        @{ Command = "ги старт оптимизация подумать"; Route = "start" },
        @{ Command = "gi start sprint"; Route = "start-sprint" },
        @{ Command = "gi plan"; Route = "task-plan" },
        @{ Command = "gi full test"; Route = "test" },
        @{ Command = "gi release test"; Route = "test" },
        @{ Command = "gi system test"; Route = "test" },
        @{ Command = "gi testing task"; Route = "test-task" },
        @{ Command = "gi задача теста"; Route = "test-task" },
        @{ Command = "ги менеджер"; Route = "task-manager" },
        @{ Command = "ги манагер"; Route = "task-manager" },
        @{ Command = "ги менеджер тест"; Route = "task-manager-test" },
        @{ Command = "gi config service off"; Route = "config-self-registration" },
        @{ Command = "gi restart"; Route = "restart" },
        @{ Command = "gi error fix"; Route = "error-fix" },
        @{ Command = "gi tools rebuild vector"; Route = "rag-rebuild" },
        @{ Command = "gi only push"; Route = "git-finish" },
        @{ Command = "ги пуш"; Route = "git-finish" }
    )
    foreach ($case in $routeCases) {
        $output = (& $resolverPath -CommandText $case.Command -PathsOnly | Out-String)
        Assert-Contains $output ("GI route: {0}" -f $case.Route) "Command '$($case.Command)' resolved incorrectly."
    }

    $gitFinishPacket = (& $resolverPath -CommandText "ги пуш" | Out-String)
    $gitFinishRoute = @($manifest.routes | Where-Object { $_.id -eq "git-finish" })
    if ($gitFinishRoute.Count -ne 1 -or
        @($gitFinishRoute[0].context_files) -contains "patterns/AGENTS_RUNTIME/15-verification.md") {
        throw "Git-finish route must not load feature-contract verification."
    }
    foreach ($needle in @(
        "Perform only the requested Git finish",
        "never classify the whole dirty",
        "does not by itself authorize product fixes",
        "does not start a project-memory audit"
    )) {
        Assert-Contains $gitFinishPacket $needle "Git-finish route is missing scope boundary text: $needle"
    }
    if ($gitFinishPacket.Contains("===== patterns/AGENTS_RUNTIME/15-verification.md =====") -or
        $gitFinishPacket.Contains("compare the scoped diff with the relevant durable")) {
        throw "Git-finish route loaded the feature-contract verification workflow."
    }
    $featureVerificationText = [System.IO.File]::ReadAllText((Join-Path $repoRoot "patterns/AGENTS_RUNTIME/15-verification.md"))
    Assert-Contains $featureVerificationText "before calling the task complete" "Development-time contract verification disappeared."
    $gitWorkflowText = [System.IO.File]::ReadAllText((Join-Path $repoRoot "patterns/GIT_WORKFLOW.md"))
    foreach ($needle in @(
        "Never infer that all dirty files",
        "authorize unrelated code or test repairs",
        "rebuilds/restarts"
    )) {
        Assert-Contains $gitWorkflowText $needle "Git workflow is missing finish-only guard text: $needle"
    }

    Assert-FileBudget "AGENTS.md" ([long]$budgets.entrypoint_max_bytes)
    Assert-FileBudget "templates/AGENTS.template.md" ([long]$budgets.template_entrypoint_max_bytes)
    Assert-FileBudget "COMMANDS.md" ([long]$budgets.command_index_max_bytes)
    Assert-FileBudget "tools/project-memory/instruction-kit.json" ([long]$budgets.metadata_max_bytes)
    Assert-FileBudget "templates/instruction-kit.template.json" ([long]$budgets.metadata_max_bytes)
    foreach ($module in Get-ChildItem -LiteralPath (Join-Path $repoRoot "patterns/AGENTS_RUNTIME") -File -Filter "*.md") {
        if ($module.Length -gt [long]$budgets.runtime_module_max_bytes) {
            throw "$($module.Name) exceeded the runtime-module budget: $($module.Length) bytes."
        }
    }

    $startPacket = (& $builderPath -CommandText "gi start" -SkipUpdateCheck | Out-String)
    Assert-Contains $startPacket "Instruction update check: skipped by caller" "Context builder omitted update status."
    Assert-Contains $startPacket "GI route: start" "Context builder omitted the start route."
    Assert-Contains $startPacket "===== PROJECT ENTRYPOINT =====" "Context builder omitted the project entrypoint."
    Assert-Contains $startPacket "===== GIT COMMIT PREFERENCES =====" "Context builder omitted commit preferences."
    Assert-Contains $startPacket "===== AGENT SYSTEM LANGUAGE =====" "Context builder omitted system-language preferences."
    Assert-Contains $startPacket "===== LATEST HANDOFF SUMMARY =====" "Context builder omitted summary state."
    Assert-Contains $startPacket "===== GIT SNAPSHOT =====" "Context builder omitted Git state."
    Assert-Contains $startPacket "Startup restore complete." "Context builder omitted the restore completion marker."
    if ($startPacket.Length -gt [int]$budgets.start_packet_max_chars) {
        throw "gi start context packet exceeded budget: $($startPacket.Length) chars."
    }
    $nonStartPacket = (& $builderPath -CommandText "gi stack" -SkipUpdateCheck | Out-String)
    if ($nonStartPacket.Contains("===== PROJECT ENTRYPOINT =====") -or
        $nonStartPacket.Contains("===== LATEST HANDOFF SUMMARY =====") -or
        $nonStartPacket.Contains("===== RUNBOOK COMMAND HINTS =====")) {
        throw "Non-start route received startup-only context sections."
    }

    [void](New-Item -ItemType Directory -Path $testRoot)
    $equal = New-UpdateFixture -Name "equal" -WithoutMigrations -MetadataJson `
        '{"instruction_kit_version":"2026.09.22.2","migration_state":{"schema_version":2,"applied_through":"2026.09.22.2__pending","additional_applied_migrations":[],"skipped_migrations":[]},"update_check":{"enabled":true}}'
    $equalOutput = (& $updaterTemplate -InstructionKitPath (Join-Path $equal.Project "tools/project-memory/instruction-kit.json") -SharedLibraryPath $equal.Source *>&1 | Out-String)
    Assert-Contains $equalOutput "Pending instruction migrations: 0" "Equal-version fast path failed."
    if ($equalOutput.Contains("No migrations folder found")) { throw "Equal-version check inspected migrations." }

    $v2 = New-UpdateFixture -Name "v2" -MetadataJson `
        '{"instruction_kit_version":"2026.09.22.1","migration_state":{"schema_version":2,"applied_through":"2026.09.22.1__already","additional_applied_migrations":[],"skipped_migrations":[]},"update_check":{"enabled":true}}'
    $v2Path = Join-Path $v2.Project "tools/project-memory/instruction-kit.json"
    $v2Output = (& $updaterTemplate -InstructionKitPath $v2Path -SharedLibraryPath $v2.Source *>&1 | Out-String)
    Assert-Contains $v2Output "Pending instruction migrations: 1" "Schema-v2 metadata did not filter the checkpoint."
    Assert-Contains $v2Output "2026.09.22.2__pending" "Schema-v2 metadata omitted the pending id."
    & $updaterTemplate -InstructionKitPath $v2Path -SharedLibraryPath $v2.Source -RecordApplied *>&1 | Out-Null
    $recorded = Get-Content -LiteralPath $v2Path -Raw | ConvertFrom-Json
    if ($recorded.migration_state.applied_through -ne "2026.09.22.2__pending") {
        throw "Recording did not advance the schema-v2 checkpoint."
    }
    if ($recorded.PSObject.Properties.Name -contains "applied_migrations") {
        throw "Recording retained the legacy migration array."
    }

    $exceptions = New-UpdateFixture -Name "exceptions" -MetadataJson `
        '{"instruction_kit_version":"2026.09.22.1","migration_state":{"schema_version":2,"applied_through":"2026.09.22.1__already","additional_applied_migrations":["2026.09.22.2__pending"],"skipped_migrations":["2026.09.22.1__already"]},"update_check":{"enabled":true}}'
    $exceptionOutput = (& $updaterTemplate -InstructionKitPath (Join-Path $exceptions.Project "tools/project-memory/instruction-kit.json") -SharedLibraryPath $exceptions.Source *>&1 | Out-String)
    Assert-Contains $exceptionOutput "Pending instruction migrations: 1" "Migration-state exceptions were not applied."
    Assert-Contains $exceptionOutput "- 2026.09.22.1__already" "Explicit skipped migration was not returned as pending."
    if ($exceptionOutput.Contains("- 2026.09.22.2__pending")) {
        throw "Explicit additional applied migration was returned as pending."
    }

    $equalSkipped = New-UpdateFixture -Name "equal-skipped" -MetadataJson `
        '{"instruction_kit_version":"2026.09.22.2","migration_state":{"schema_version":2,"applied_through":"2026.09.22.2__pending","additional_applied_migrations":[],"skipped_migrations":["2026.09.22.2__pending"]},"update_check":{"enabled":true}}'
    $equalSkippedOutput = (& $updaterTemplate -InstructionKitPath (Join-Path $equalSkipped.Project "tools/project-memory/instruction-kit.json") -SharedLibraryPath $equalSkipped.Source *>&1 | Out-String)
    Assert-Contains $equalSkippedOutput "Pending instruction migrations: 1" "Equal-version fast path ignored an explicit skipped migration."
    Assert-Contains $equalSkippedOutput "2026.09.22.2__pending" "Equal-version skipped migration id was omitted."

    $semanticSource = Join-Path $testRoot "semantic-source"
    $semanticProject = Join-Path $testRoot "semantic-project"
    [void](New-Item -ItemType Directory -Path (Join-Path $semanticSource "migrations") -Force)
    [void](New-Item -ItemType Directory -Path (Join-Path $semanticProject "tools/project-memory") -Force)
    [System.IO.File]::WriteAllText((Join-Path $semanticSource "VERSION.md"), 'Current accepted version: `2026.09.22.10`', [System.Text.UTF8Encoding]::new($false))
    foreach ($id in @("2026.09.22.9__old", "2026.09.22.10__new")) {
        [System.IO.File]::WriteAllText((Join-Path $semanticSource "migrations/$id.md"), "# $id", [System.Text.UTF8Encoding]::new($false))
    }
    $semanticMetadataPath = Join-Path $semanticProject "tools/project-memory/instruction-kit.json"
    [System.IO.File]::WriteAllText(
        $semanticMetadataPath,
        '{"instruction_kit_version":"2026.09.22.9","migration_state":{"schema_version":2,"applied_through":"2026.09.22.9__old","additional_applied_migrations":[],"skipped_migrations":[]},"update_check":{"enabled":true}}',
        [System.Text.UTF8Encoding]::new($false)
    )
    $semanticOutput = (& $updaterTemplate -InstructionKitPath $semanticMetadataPath -SharedLibraryPath $semanticSource *>&1 | Out-String)
    Assert-Contains $semanticOutput "Pending instruction migrations: 1" "Migration ids were not compared by semantic version."
    Assert-Contains $semanticOutput "2026.09.22.10__new" "Semantic migration ordering omitted version .10."
    if ($semanticOutput.Contains("- 2026.09.22.9__old")) { throw "Semantic migration ordering returned version .9 after checkpoint .9." }
    & $updaterTemplate -InstructionKitPath $semanticMetadataPath -SharedLibraryPath $semanticSource -RecordApplied *>&1 | Out-Null
    $semanticRecorded = Get-Content -LiteralPath $semanticMetadataPath -Raw | ConvertFrom-Json
    if ($semanticRecorded.migration_state.applied_through -ne "2026.09.22.10__new") {
        throw "Recording did not select the semantically latest migration id."
    }

    $legacy = New-UpdateFixture -Name "legacy" -MetadataJson `
        '{"instruction_kit_version":"2026.09.22.1","applied_migrations":["2026.09.22.1__already"],"update_check":{"enabled":true}}'
    $legacyOutput = (& $updaterTemplate -InstructionKitPath (Join-Path $legacy.Project "tools/project-memory/instruction-kit.json") -SharedLibraryPath $legacy.Source *>&1 | Out-String)
    Assert-Contains $legacyOutput "Pending instruction migrations: 1" "Legacy metadata compatibility failed."
    Assert-Contains $legacyOutput "2026.09.22.2__pending" "Legacy metadata omitted the pending id."

    Write-Output "GI routing, context budgets, builder, and migration-state checks passed."
}
finally {
    if (Test-Path -LiteralPath $testRoot -PathType Container) {
        $resolvedTestRoot = (Resolve-Path -LiteralPath $testRoot).Path
        $resolvedTempRoot = (Resolve-Path -LiteralPath ([System.IO.Path]::GetTempPath())).Path
        if (-not $resolvedTestRoot.StartsWith($resolvedTempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove test data outside the system temp directory: $resolvedTestRoot"
        }
        Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force
    }
}
