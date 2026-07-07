# General Instructions Index

Reusable instructions in this repository are grouped by job.

## User Documents

- `CHANGELOG.md`: accepted instruction-kit changes by version.
- `config/gi-main.json`: bootstrap pointer to the local GI config service.
- `COMMANDS.md`: user-facing agent prompts and helper commands for
  bootstrapping projects, restoring context, configuring Git commit languages
  and agent working languages, checking instruction updates, and maintaining
  this library.
- `USER_GUIDE.md`: short user-facing overview of the main instructions and
  rules.
- `VERSION.md`: current accepted instruction-kit version.

## Project Memory

- `tools/project-memory/README.md`: local project-memory usage, including the
  generated SQLite index workflow.
- `tools/project-memory/build_project_memory_index.py`: stdlib-only SQLite
  indexer for fast rebuilds from git tracked files and targeted searches.
- `tools/project-memory/build_chroma_index.py`: optional Chroma adapter that
  builds and queries a generated local vector index from exported chunks.
- `tools/project-memory/rag_check.py`: local RAG health and retrieval eval
  runner for SQLite, semantic corpus, and Chroma consistency checks.
- `tools/project-memory/retrieval-evals.json`: reviewable retrieval eval cases
  for recurring keyword, semantic, and hybrid lookup expectations.
- `tools/project-memory/architecture-migrations.md`: durable history of major
  architecture rewrites and platform migrations for this repository.

## Core Playbooks

- `DEVELOPMENT_PLAN.md`: planned improvements for this shared instruction
  library.
- `GENERAL_DEVELOPMENT_PLAYBOOK.md`: baseline process for starting and
  maintaining a project with an AI agent.

## Patterns

- `patterns/AGENTS_RUNTIME/`: task-routed runtime modules used by compact root
  and copied `AGENTS.md` entrypoints. The modules cover project purpose, rule
  precedence, authoring, Windows commands, token economy, startup/scope,
  config-service and task-manager flows, operations commands, private scope,
  language preferences, UI focus, progress updates, update intake,
  verification, and git policy.
- `patterns/AGENT_EXPERIENCE_SQLITE.md`: local SQLite memory/index pattern for
  AI-agent experience, with Markdown export for review.
- `patterns/AGENT_HARNESS_RUNTIME.md`: runtime pattern for building or auditing
  model-tool-observation loops, tool permissions, compaction, connectors, evals,
  and production agent harnesses.
- `patterns/AGENT_ROLE_OFFICE.md`: extensible specialist-role office pattern
  for routing work through narrow professional lenses such as product owner,
  tech lead, C#/.NET backend, frontend, UI/UX design, visual art, QA,
  DevOps/release, security, and documentation.
- `patterns/AI_ENGINEERING_BENCHMARKS.md`: benchmark pattern for proving AI
  engineering cost reduction while preserving task quality.
- `patterns/ARCHITECTURE_AND_CODE_QUALITY.md`: architecture and code-quality
  baseline for OOP, SOLID, DRY, clean-code, separation of concerns,
  interfaces/adapters/contracts, abstraction discipline, and verification.
- `patterns/API_KEY_SECRET_SAFETY.md`: API-key and secret-safety rules for
  keeping credentials out of code, client bundles, logs, generated artifacts,
  and project memory; separating dev/staging/prod credentials; using managed
  production secret stores; rotating leaks; monitoring usage; and applying
  provider-supported scoping and network restrictions.
- `patterns/COHERENT_BATCH_VERIFICATION.md`: batch-completion rules for
  source-of-truth consistency, durable memory writeback, scoped diffs, and
  evidence-backed checks.
- `patterns/TECHNOLOGY_STACK_INVENTORY.md`: project-memory rules for keeping a
  verified technology stack inventory with languages, runtimes, frameworks,
  package managers, build/test tools, storage, services, commands, evidence,
  and gaps.
- `patterns/CONFIGURATION_BOUNDARIES.md`: configuration-boundary rules for
  keeping deploy, user, runtime, machine, service, credential, path,
  feature-flag, and operational values out of application logic.
- `patterns/DEVELOPMENT_TOOL_PRODUCT_BOUNDARIES.md`: rules for keeping
  orchestrators, task managers, agent harnesses, generators, workflow logs,
  scaffolding tools, and tooling folders product-agnostic, free of demo
  hard-code, separate from generated outputs, and architected with clear
  SOLID/module boundaries.
- `patterns/EXTERNAL_DOCUMENTATION_RETRIEVAL.md`: rules for using Context7 or
  similar external current-docs retrieval tools without leaking private project
  data or replacing project memory and official sources.
- `patterns/FIRST_MESSAGE_HANDLING.md`: first-message title detection and shared
  instruction bootstrap behavior.
- `patterns/FEATURE_WORKFLOW_CONTRACTS.md`: project-local contracts for agreed
  feature workflows, branching states, background work, and user-visible
  behavior guarantees.
- `patterns/FULL_RAG_AGENT_PLATFORM.md`: architecture pattern for a LangGraph
  agent platform with structured memory, semantic retrieval, tracing, evals,
  and optional n8n automation.
- `patterns/GIT_WORKFLOW.md`: git policy, explicit commit requests, dirty
  worktrees, and commit-message language preferences.
- `patterns/INSTRUCTION_KIT_MIGRATIONS.md`: migration-style update workflow for
  copied project instruction kits.
- `patterns/MODEL_ROUTING_AND_COST_CONTROL.md`: model-routing and cost-control
  pattern for agent applications that use multiple models, tools, RAG, prompt
  caching, and explicit budget limits.
- `patterns/PROJECT_TESTING_STRATEGY.md`: project-aware testing strategy for
  new features, bug fixes, smoke checks, and release confidence.
- `patterns/PROJECT_FTP_DEPLOY.md`: project-local FTP/FTPS/SFTP deploy config
  and `gi ftp` upload workflow.
- `patterns/PROJECT_DEV_PROD_SERVICES.md`: development versus production
  service-folder workflow for live online services connected to remote APIs,
  including `gi prod` publication rules.
- `patterns/PROJECT_DOCUMENTATION_LAYERS.md`: rules for keeping
  human-facing project documentation separate from implementation-driving
  project memory.
- `patterns/PROJECT_MEMORY_SPECIFICATIONS.md`: portable project-memory
  specifications for product behavior, feature algorithms, business logic,
  connected-project registers, architecture migrations, and SQL/vector
  activation limits.
- `patterns/QUERY_PROMPT_NORMALIZATION_BOUNDARIES.md`: rules for keeping
  translation maps, synonym dictionaries, query expansion, prompt templates,
  ranking thresholds, and model-specific search behavior in resources, config,
  adapters, or retrieval pipelines instead of inline hard-code.
- `patterns/RAG_SYSTEM_STRUCTURE.md`: expandable RAG structure that separates
  source corpus, structured memory, retrieval adapters, context packets,
  tracing, evals, and writeback.
- `patterns/RAG_STARTUP_FLOW.md`: token-conscious startup retrieval flow for
  restoring only task-relevant context.
- `patterns/SEMANTIC_RAG_RETRIEVAL.md`: embedding and semantic retrieval rules
  for chunk export, model metadata, hybrid search, evals, and safety.
- `patterns/SERVICE_DISCOVERY_CONFIG.md`: config-service bootstrap,
  service-identity verification, mismatch handling, and local override rules.
- `patterns/SENIOR_AGENT_ENGINEERING_STANDARD.md`: compact senior-engineering
  execution standard that connects context loading, architecture boundaries,
  configuration discipline, coherent batches, verification, project-memory
  updates, and runtime enforcement.
- `patterns/SHARED_INSTRUCTIONS_BOOTSTRAP.md`: how to deploy local project
  instruction files from this shared library when the user provides its path.
- `patterns/SKILL_MODULES.md`: when to use rules, patterns, templates, or
  self-contained skill modules.
- `patterns/STARTUP_PRODUCT_ENGINEERING.md`: startup-oriented delivery pattern
  for business-first product outcomes, deadline-aware implementation,
  pragmatic design, C#/.NET async and concurrency expectations, frontend
  framework discipline, professional English communication, and review focus.

## Skills

- `skills/task-manager-plans/SKILL.md`: optional skill for reading, writing, and
  syncing plans through configured task managers, with a WorkNest adapter under
  `skills/task-manager-plans/references/managers/worknest.md`.

## Templates

- `templates/AGENTS.template.md`: starter root `AGENTS.md` for a project.
- `templates/AGENT_RUNBOOK.template.md`: starter project runbook.
- `templates/AGENT_WORKING_AGREEMENTS.template.md`: starter working agreements.
- `templates/AI_ENGINEERING_BENCHMARK.template.md`: copyable form for measuring
  raw and optimized AI engineering workflows.
- `templates/check-instruction-kit-updates.template.ps1`: project command for
  checking accepted instruction-kit migrations.
- `templates/config-service-local.template.json`: starter project-local
  bootstrap override for the GI config service.
- `templates/ARCHITECTURE_MIGRATIONS.template.md`: starter project-memory file
  for recording major architecture rewrites and platform migrations.
- `templates/CONNECTED_PROJECTS.template.md`: starter connected-projects
  register for external repositories, services, docs, and upstream tools.
- `templates/project-memory-README.template.md`: starter memory folder README.
- `templates/rag-system.template.json`: project-local RAG configuration shape
  for source groups, exclusions, structured memory, retrieval adapters, context
  packets, and writeback.
- `templates/pending-tasks.template.md`: starter active task checklist.
- `templates/STUDY_PLAN.template.md`: starter study plan for mapping a project.
- `templates/agent-start.template.ps1`: compact startup script template with
  line guards and `git diff --stat`.
- `templates/FEATURE_TEST_PLAN.template.md`: copyable plan for verifying a new
  feature or risky change.
- `templates/FEATURE_WORKFLOW_CONTRACT.template.md`: copyable contract for
  documenting a feature's agreed runtime workflow and behavior guarantees.
- `templates/ftp.local.template.json`: redacted starter shape for a
  project-local `tools/deploy/ftp.local.json` upload config.
- `templates/git-preferences.template.json`: project-local commit-message
  language preference defaults.
- `templates/system-preferences.template.json`: project-local agent working
  language preference defaults.
- `templates/select-project-language.template.ps1`: interactive project setup
  command for ordered language choices covering project working environment,
  commit messages, and tasks.
- `templates/gitignore-agent-memory.template`: ignore snippet for local agent
  memory and runtime noise.
- `templates/instruction-kit.template.json`: copied provenance and local update
  check configuration for project instruction kits.
- `templates/select-git-commit-languages.template.ps1`: interactive project
  setup command for commit-message language preferences.
- `templates/select-system-language.template.ps1`: interactive project setup
  command for the agent's user-facing working language.
- `templates/semantic-retrieval-evals.template.md`: starter eval set for
  semantic and hybrid retrieval quality.
- `templates/SKILL.template.md`: starter `SKILL.md` for a self-contained agent
  skill module.
- `templates/SUMMARY.template.md`: handoff summary template.
- `templates/task-managers.template.json`: starter project-local task-manager
  configuration for optional plan sync skills.
- `templates/TECHNOLOGY_STACK.template.md`: starter project-memory technology
  stack inventory.

## Update Intake

- `updates/`: maintenance-only dated recommendations for this
  `general-instructions` repository. External projects must not read this folder
  during startup or bootstrap.
- `updates/USER_REPORTED_AGENT_BUG_LOG.md`: maintenance-only rolling log for
  recurring user-reported agent-rule failures and their follow-up status.

## Migrations

- `migrations/`: accepted ordered instruction-kit migrations for consuming
  projects. External projects may read this folder only when checking or applying
  instruction updates.

## Checklists

- `checklists/NEW_PROJECT_AGENT_SETUP.md`: quick checklist for adding agent
  support to a project.

## Library Rules

- Keep files project-agnostic.
- Prefer templates when the target project needs its own local decisions.
- Link new files here when they become part of the reusable library.
