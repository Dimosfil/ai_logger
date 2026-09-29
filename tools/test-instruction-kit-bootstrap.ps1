[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$installer = Join-Path $repoRoot "tools/install-instruction-kit.ps1"
$testRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("gi-bootstrap-test-" + [guid]::NewGuid().ToString("N"))
$forms = @(
    "https://github.com/Dimosfil/general-instructions.git",
    "Dimosfil/general-instructions.git",
    "[Dimosfil/general-instructions.git](https://github.com/Dimosfil/general-instructions.git)",
    $repoRoot
)
$requiredFiles = @(
    "AGENTS.md",
    "BOOTSTRAP.md",
    "COMMANDS.md",
    "config/gi-command-routes.json",
    "config/gi-context-budgets.json",
    "tools/AGENT_WORKING_AGREEMENTS.md",
    "tools/AGENT_RUNBOOK.md",
    "tools/agent-start.ps1",
    "tools/get-gi-context.ps1",
    "tools/resolve-gi-command.ps1",
    "tools/project-memory/instruction-kit.json",
    "tools/project-memory/rag-system.json",
    "tools/project-memory/code_intelligence.py",
    "patterns/CODE_INTELLIGENCE_ADAPTERS.md",
    "patterns/GI_COMMAND_CONTRACTS.md",
    "patterns/MODULAR_SERVICE_ENGINEERING.md",
    "templates/SYSTEM_MAP.template.md",
    "templates/MODULE_PASSPORT.template.md",
    "templates/MODULE_CONTRACT.template.md",
    "patterns/AGENTS_RUNTIME/07-startup.md",
    "patterns/AGENTS_RUNTIME/07-scope-and-evidence.md",
    "patterns/AGENTS_RUNTIME/08-config-service.md",
    "patterns/AGENTS_RUNTIME/08-task-manager.md",
    "patterns/AGENTS_RUNTIME/08-sprint.md",
    "patterns/AGENTS_RUNTIME/09-production.md",
    "patterns/AGENTS_RUNTIME/09-deploy-gateway.md",
    "patterns/AGENTS_RUNTIME/09-ftp.md",
    "patterns/AGENTS_RUNTIME/09-runtime-and-defaults.md",
    "patterns/AGENTS_RUNTIME/09-testing.md",
    "patterns/AGENTS_RUNTIME/09-build-and-install.md",
    "patterns/AGENTS_RUNTIME/09-project-memory-operations.md"
)

try {
    [void](New-Item -ItemType Directory -Path $testRoot)
    for ($index = 0; $index -lt $forms.Count; $index++) {
        $target = Join-Path $testRoot ("case-" + $index)
        [void](New-Item -ItemType Directory -Path $target)

        if ($index -eq 2) {
            [System.IO.File]::WriteAllText(
                (Join-Path $target "AGENTS.md"),
                "# Existing project instructions",
                [System.Text.UTF8Encoding]::new($false)
            )
        }

        & $installer -Source $forms[$index] -SourceRoot $repoRoot -TargetPath $target | Out-Null

        foreach ($requiredFile in $requiredFiles) {
            $requiredPath = Join-Path $target $requiredFile
            if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
                throw "Bootstrap form '$($forms[$index])' did not create '$requiredFile'."
            }
        }
        if (Test-Path -LiteralPath (Join-Path $target ".git")) {
            throw "Bootstrap form '$($forms[$index])' created a Git repository."
        }
        if ($index -eq 2) {
            $agentsText = [System.IO.File]::ReadAllText((Join-Path $target "AGENTS.md"))
            if ($agentsText -ne "# Existing project instructions") {
                throw "The installer overwrote existing project instructions."
            }
        }

        $metadata = Get-Content -Raw -LiteralPath (Join-Path $target "tools/project-memory/instruction-kit.json") | ConvertFrom-Json
        if ($metadata.update_check.source_repo -ne "https://github.com/Dimosfil/general-instructions.git") {
            throw "Bootstrap form '$($forms[$index])' did not record the canonical source repository."
        }
        if ($metadata.update_check.auto_apply_pending_migrations -ne $true) {
            throw "Bootstrap form '$($forms[$index])' did not enable startup migration auto-application."
        }
        if ($metadata.config_service.enabled -ne $false) {
            throw "Bootstrap form '$($forms[$index])' did not default config-service integration to off."
        }
        if ($metadata.migration_state.schema_version -ne 2) {
            throw "Bootstrap form '$($forms[$index])' did not install migration-state schema v2."
        }
        if ($metadata.migration_state.applied_through -ne '2026.09.28.2__add_modular_service_agent_guidance') {
            throw "Bootstrap form '$($forms[$index])' did not record the accepted migration checkpoint."
        }
        if ($metadata.PSObject.Properties.Name -contains 'applied_migrations') {
            throw "Bootstrap form '$($forms[$index])' retained the legacy migration array."
        }

        $ragConfig = Get-Content -Raw -LiteralPath (Join-Path $target "tools/project-memory/rag-system.json") | ConvertFrom-Json
        if ($ragConfig.code_intelligence.enabled -ne $false) {
            throw "Bootstrap form '$($forms[$index])' did not default code intelligence to off."
        }

        $configRuleText = [System.IO.File]::ReadAllText(
            (Join-Path $target "patterns/AGENTS_RUNTIME/08-config-service.md")
        )
        $commandsText = [System.IO.File]::ReadAllText((Join-Path $target "COMMANDS.md"))
        foreach ($needle in @(
            'config_service.enabled',
            'Fresh GI bootstraps must create',
            'gi config on',
            'gi config off'
        )) {
            if (-not (($configRuleText + "`n" + $commandsText).Contains($needle))) {
                throw "Bootstrap form '$($forms[$index])' is missing config-service toggle rule text: $needle"
            }
        }

        $startupRuleText = [System.IO.File]::ReadAllText(
            (Join-Path $target "patterns/AGENTS_RUNTIME/07-startup.md")
        )
        foreach ($needle in @(
            'update_check.enabled: true',
            'auto_apply_pending_migrations',
            'Finding a newer version is not a completed startup',
            'If the versions are equal',
            'stop the update check without reading'
        )) {
            if (-not $startupRuleText.Contains($needle)) {
                throw "Bootstrap form '$($forms[$index])' is missing startup auto-application rule text: $needle"
            }
        }

        $agentStartText = [System.IO.File]::ReadAllText((Join-Path $target "tools/agent-start.ps1"))
        if (-not $agentStartText.Contains('tools/get-gi-context.ps1')) {
            throw "Bootstrap form '$($forms[$index])' did not delegate startup to the one-call context builder."
        }

        $resolverOutput = (& (Join-Path $target "tools/resolve-gi-command.ps1") `
            -CommandText "gi start sprint" -PathsOnly | Out-String)
        if (-not $resolverOutput.Contains("GI route: start-sprint")) {
            throw "Bootstrap form '$($forms[$index])' did not install a working longest-prefix GI resolver."
        }
        $installedManifest = Get-Content -Raw -LiteralPath (Join-Path $target "config/gi-command-routes.json") | ConvertFrom-Json
        foreach ($route in $installedManifest.routes) {
            $routeOutput = (& (Join-Path $target "tools/resolve-gi-command.ps1") `
                -CommandText ([string]$route.aliases[0]) -PathsOnly | Out-String)
            if (-not $routeOutput.Contains("GI route: $($route.id)")) {
                throw "Bootstrap form '$($forms[$index])' could not resolve installed route '$($route.id)'."
            }
        }

        $summaryDirectory = Join-Path $target "tools/summary"
        $olderSummaryPath = Join-Path $summaryDirectory "2026-09-20_OLDER_AGENT_WORK_SUMMARY.md"
        $newerSummaryPath = Join-Path $summaryDirectory "2026-09-21_NEWER_AGENT_WORK_SUMMARY.md"
        $ignoredSummaryPath = Join-Path $summaryDirectory "9999-12-31_IGNORED.md"
        [System.IO.File]::WriteAllText($olderSummaryPath, "OLDER SUMMARY", [System.Text.UTF8Encoding]::new($false))
        [System.IO.File]::WriteAllText($newerSummaryPath, ("NEWER SUMMARY " + ("x" * 50000)), [System.Text.UTF8Encoding]::new($false))
        [System.IO.File]::WriteAllText($ignoredSummaryPath, "IGNORED SUMMARY", [System.Text.UTF8Encoding]::new($false))
        (Get-Item -LiteralPath $olderSummaryPath).LastWriteTime = (Get-Date).AddHours(-2)
        (Get-Item -LiteralPath $newerSummaryPath).LastWriteTime = (Get-Date).AddHours(-1)
        (Get-Item -LiteralPath $ignoredSummaryPath).LastWriteTime = Get-Date
        [System.IO.File]::WriteAllText(
            (Join-Path $target "tools/project-memory/index_project.py"),
            "# startup hint fixture",
            [System.Text.UTF8Encoding]::new($false)
        )

        Push-Location $testRoot
        try {
            $contextOutput = (& (Join-Path $target "tools/get-gi-context.ps1") `
                -CommandText "gi start" -SkipUpdateCheck | Out-String)
        }
        finally {
            Pop-Location
        }
        foreach ($needle in @(
            "GI route: start",
            "===== PROJECT ENTRYPOINT =====",
            "===== WORKING AGREEMENTS =====",
            "showing first 80 lines only.",
            "===== GIT COMMIT PREFERENCES =====",
            "===== AGENT SYSTEM LANGUAGE =====",
            "===== LATEST HANDOFF SUMMARY =====",
            "NEWER SUMMARY",
            "===== GIT SNAPSHOT =====",
            "===== RUNBOOK COMMAND HINTS =====",
            "===== PROJECT MEMORY =====",
            "Startup restore complete."
        )) {
            if (-not $contextOutput.Contains($needle)) {
                throw "Bootstrap form '$($forms[$index])' context builder omitted: $needle"
            }
        }
        if ($contextOutput.Contains("IGNORED SUMMARY")) {
            throw "Bootstrap form '$($forms[$index])' selected an unrelated summary Markdown file."
        }
        $contextBudgets = Get-Content -LiteralPath (Join-Path $target "config/gi-context-budgets.json") -Raw | ConvertFrom-Json
        if ($contextOutput.Length -gt [int]$contextBudgets.start_packet_max_chars) {
            throw "Bootstrap form '$($forms[$index])' exceeded the installed start-packet budget: $($contextOutput.Length) chars."
        }
        if (-not $contextOutput.Contains("context truncated:")) {
            throw "Bootstrap form '$($forms[$index])' did not mark truncated oversized startup context."
        }

        if ($index -eq 0) {
            $budgetFile = Join-Path $target "config/gi-context-budgets.json"
            $budgetText = [System.IO.File]::ReadAllText($budgetFile)
            $tightBudgets = $budgetText | ConvertFrom-Json
            $tightBudgets.start_packet_max_chars = 5000
            [System.IO.File]::WriteAllText(
                $budgetFile,
                (($tightBudgets | ConvertTo-Json -Depth 100) + [Environment]::NewLine),
                [System.Text.UTF8Encoding]::new($false)
            )
            try {
                $tightContext = (& (Join-Path $target "tools/get-gi-context.ps1") -CommandText "gi start" -SkipUpdateCheck | Out-String)
            }
            finally {
                [System.IO.File]::WriteAllText($budgetFile, $budgetText, [System.Text.UTF8Encoding]::new($false))
            }
            if ($tightContext.Length -gt 5000) { throw "Final startup packet hard cap was not enforced." }
            if (-not $tightContext.Contains("context packet truncated:") -or -not $tightContext.Contains("Startup restore complete.")) {
                throw "Hard-capped startup packet omitted its truncation or completion marker."
            }

            & git -C $target init --quiet
            & git -C $target config core.autocrlf true
            $crlfFixture = Join-Path $target "crlf-fixture.txt"
            [System.IO.File]::WriteAllText($crlfFixture, "first`r`nsecond`r`n", [System.Text.UTF8Encoding]::new($false))
            & git -C $target add -- crlf-fixture.txt
            & git -C $target -c user.name="GI Test" -c user.email="gi-test@example.invalid" commit --quiet -m "Add CRLF fixture"
            $crlfContext = (& (Join-Path $target "tools/get-gi-context.ps1") -CommandText "gi start" -SkipUpdateCheck | Out-String)
            if ($crlfContext.Contains(" M crlf-fixture.txt") -or $crlfContext.Contains("crlf-fixture.txt |")) {
                throw "Context builder reported a clean CRLF file as modified."
            }

            $metadataPath = Join-Path $target "tools/project-memory/instruction-kit.json"
            $metadataBeforeFailureTest = [System.IO.File]::ReadAllText($metadataPath)
            $brokenSource = Join-Path $testRoot "broken-update-source"
            [void](New-Item -ItemType Directory -Path $brokenSource -Force)
            $failureMetadata = $metadataBeforeFailureTest | ConvertFrom-Json
            $failureMetadata.update_check.shared_library_path = $brokenSource
            $failureMetadata.update_check.source_repo = ""
            [System.IO.File]::WriteAllText(
                $metadataPath,
                (($failureMetadata | ConvertTo-Json -Depth 100) + [Environment]::NewLine),
                [System.Text.UTF8Encoding]::new($false)
            )
            $failureText = ""
            try {
                $failureText = (& (Join-Path $target "tools/get-gi-context.ps1") -CommandText "gi start" *>&1 | Out-String)
                throw "Context builder did not fail when the update check failed."
            }
            catch {
                $failureText = ($failureText + "`n" + $_.Exception.Message)
            }
            finally {
                [System.IO.File]::WriteAllText($metadataPath, $metadataBeforeFailureTest, [System.Text.UTF8Encoding]::new($false))
            }
            if (-not $failureText.Contains("Instruction update check failed")) {
                throw "Context builder did not propagate the update-check failure."
            }
            if ($failureText.Contains("Startup restore complete.")) {
                throw "Context builder reported startup completion after a failed update check."
            }
        }

        $secretRuleText = [System.IO.File]::ReadAllText(
            (Join-Path $target "patterns/API_KEY_SECRET_SAFETY.md")
        )
        $workingAgreementsText = [System.IO.File]::ReadAllText(
            (Join-Path $target "tools/AGENT_WORKING_AGREEMENTS.md")
        )
        foreach ($needle in @(
            'but do not treat that fact',
            'mark only the affected authenticated operation blocked or unverified'
        )) {
            if (-not $secretRuleText.Contains($needle)) {
                throw "Bootstrap form '$($forms[$index])' is missing non-blocking secret rule text: $needle"
            }
        }
        if (-not $workingAgreementsText.Contains('Do not treat a credential pasted into chat as an automatic blocker')) {
            throw "Bootstrap form '$($forms[$index])' is missing the working-agreement secret rule."
        }

        $gitIgnorePath = Join-Path $target ".gitignore"
        $gitIgnoreBefore = [System.IO.File]::ReadAllText($gitIgnorePath)
        $metadata.PSObject.Properties.Remove("config_service")
        $metadataJson = $metadata | ConvertTo-Json -Depth 100
        [System.IO.File]::WriteAllText(
            (Join-Path $target "tools/project-memory/instruction-kit.json"),
            $metadataJson + [Environment]::NewLine,
            [System.Text.UTF8Encoding]::new($false)
        )
        & $installer -Source $forms[$index] -SourceRoot $repoRoot -TargetPath $target | Out-Null
        $gitIgnoreAfter = [System.IO.File]::ReadAllText($gitIgnorePath)
        if ($gitIgnoreAfter -ne $gitIgnoreBefore) {
            throw "Bootstrap form '$($forms[$index])' is not idempotent for .gitignore."
        }
        $legacyMetadata = Get-Content -Raw -LiteralPath (Join-Path $target "tools/project-memory/instruction-kit.json") | ConvertFrom-Json
        if ($legacyMetadata.PSObject.Properties.Name -contains "config_service") {
            throw "Bootstrap form '$($forms[$index])' changed a legacy project's absent config-service toggle."
        }
    }

    $readmeText = [System.IO.File]::ReadAllText((Join-Path $repoRoot "README.md"))
    $bootstrapText = [System.IO.File]::ReadAllText((Join-Path $repoRoot "BOOTSTRAP.md"))
    foreach ($needle in @(
        '[Dimosfil/general-instructions.git](https://github.com/Dimosfil/general-instructions.git)',
        'patterns/SHARED_INSTRUCTIONS_BOOTSTRAP.md',
        'never means ordinary `git init`'
    )) {
        if (-not ($readmeText + "`n" + $bootstrapText).Contains($needle)) {
            throw "Bootstrap entrypoint is missing required text: $needle"
        }
    }

    Write-Output "GI bootstrap contract checks passed for $($forms.Count) source forms."
} finally {
    if (Test-Path -LiteralPath $testRoot -PathType Container) {
        $resolvedTestRoot = (Resolve-Path -LiteralPath $testRoot).Path
        $resolvedTempRoot = (Resolve-Path -LiteralPath ([System.IO.Path]::GetTempPath())).Path
        if (-not $resolvedTestRoot.StartsWith($resolvedTempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove test data outside the system temp directory: $resolvedTestRoot"
        }
        Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force
    }
}
