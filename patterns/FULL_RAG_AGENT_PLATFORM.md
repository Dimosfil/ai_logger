# Full RAG Agent Platform

Use this pattern when a project needs a real agent platform, not only Markdown
instructions or ad hoc memory files.

## Goal

Build a token-conscious agent runtime that can:

- orchestrate task flow through explicit states;
- retrieve only task-relevant instructions and project knowledge;
- keep structured memory outside chat history;
- trace retrieval, prompts, tools, failures, and outcomes;
- automate external workflows only when they are clearly outside the agent core.

Do not treat vector search as the whole RAG system. Chroma, Qdrant, and
pgvector are retrieval storage options; the full system also needs source
selection, chunking, embeddings, metadata, ranking, prompt assembly,
observability, tests, and update workflows.

Use `patterns/RAG_SYSTEM_STRUCTURE.md` as the base structure for source corpus,
structured memory, retrieval adapters, context packets, and writeback. Use this
file when the project needs to grow that structure into a full agent platform
with orchestration, tracing, evals, and optional automation.

## Target Stack

- Core orchestration: LangGraph.
- Memory: SQLite for local single-user MVPs; PostgreSQL when concurrency,
  multiple projects, permissions, or service operation matter.
- RAG: Chroma for the simplest local vector MVP; Qdrant for a dedicated local
  or service-grade retrieval service; pgvector when PostgreSQL is already the
  main operational database.
- Monitoring: LangSmith free for graph traces, prompt packets, tool calls,
  retrieval quality, failures, and evaluation runs.
- Automation: n8n only for external schedules, notifications, issue/task sync,
  webhooks, and cross-service workflows.

## Product Boundary

Keep these responsibilities in the agent platform:

- task routing and graph state;
- context retrieval and prompt assembly;
- memory reads and writes;
- tool execution policy;
- verification and failure handling;
- trace and audit records.

Keep these responsibilities out of the platform unless explicitly needed:

- broad project management UI;
- long-running business workflows better owned by n8n or a task manager;
- application product databases;
- secrets storage;
- raw dumps of private local telemetry;
- cross-project scanning that bypasses configured service discovery.

## Memory Versus RAG

Use structured memory for facts and state:

- user and project preferences;
- task status and active plans;
- accepted decisions;
- service registry references;
- index metadata and content hashes;
- audit events;
- known failures and verified fixes.

Use RAG for source-grounded text retrieval:

- root and local `AGENTS.md` files;
- `INDEX.md`, playbooks, patterns, checklists, and templates;
- accepted migrations and update intake after review;
- project memory notes and handoff summaries;
- task-specific runbooks and troubleshooting notes.

Do not use a vector store as a replacement for structured memory. Store
workflow state in SQLite or PostgreSQL and retrieve text evidence through the
RAG layer.

## Storage Choice

Choose the smallest storage mode that satisfies the current operating needs:

- SQLite only: use for local MVPs that need structured memory, content hashes,
  FTS5 keyword search, and reviewable Markdown export.
- SQLite plus Chroma: use when local semantic search is needed but there is no
  dedicated service requirement.
- PostgreSQL plus pgvector: use when metadata, permissions, operational data,
  and vector search should live in one PostgreSQL-backed service.
- PostgreSQL plus Qdrant: use when structured memory and vector retrieval should
  scale independently or retrieval needs a dedicated API, payload filters,
  snapshots, and HNSW tuning.

Plain SQLite is not enough for full semantic RAG by itself because it does not
provide efficient vector nearest-neighbor search without extensions. It remains
useful for metadata, preferences, state, FTS5 keyword search, hashes, and local
agent memory.

Recommended `gi` MVP:

- SQLite for structured memory, file hashes, FTS5 keyword retrieval, and local
  audit events.
- Chroma for local semantic retrieval when conceptual search becomes necessary.
- A storage adapter boundary so the same retrieval interface can later point to
  Qdrant or pgvector without changing agent prompts or task flows.

Do not introduce PostgreSQL, Qdrant, or n8n until the local MVP shows a real
need for concurrency, service operation, stronger vector filtering, snapshots,
external automation, or shared multi-project access.

## Structured Memory Schema

Start with small tables that map to durable agent responsibilities:

- `projects`: project id, name, root path hash or stable slug, instruction kit
  version, created time, updated time.
- `preferences`: project id, scope, key, value JSON, source path, updated time.
- `tasks`: project id, task id, title, status, current objective, blocker,
  updated time.
- `decisions`: project id, topic, decision, rationale, evidence paths JSON,
  confidence, created time.
- `documents`: project id, source path, source type, hash, modified time,
  indexed time, include/exclude status.
- `chunks`: document id, chunk id, heading path, text, token estimate, hash,
  metadata JSON.
- `retrieval_events`: query, task intent, filters JSON, selected chunk ids JSON,
  rejected reason summary, token estimate, created time.
- `tool_events`: task id, tool name, policy class, status, bounded result
  summary, evidence paths JSON, created time.
- `failures`: project id, symptom, cause, fix, evidence paths JSON, status,
  updated time.
- `audit_events`: actor, action, target, status, metadata JSON, created time.

Keep embeddings in the vector store or in a separate extension-backed table.
Keep enough chunk metadata in SQLite or PostgreSQL to rebuild vector indexes
from source documents.

## Embeddings

Select the embedding model per deployment, but keep these constraints stable:

- record embedding model name, dimensions, provider, and created time in index
  metadata;
- never mix embeddings from different models in the same vector collection
  without a collection version boundary;
- re-embed only chunks whose content hash or embedding model changed;
- keep a keyword retrieval path for exact command names, paths, error strings,
  and symbols;
- treat embeddings as generated artifacts that can be rebuilt from approved
  source text.

Use provider-specific model choices in project-local configuration or a runtime
registry, not as hard-coded shared-library policy.

## Source Corpus

Start with explicit source groups:

- shared instructions: `AGENTS.md`, `INDEX.md`,
  `GENERAL_DEVELOPMENT_PLAYBOOK.md`, `COMMANDS.md`;
- reusable patterns: `patterns/`;
- operational checklists: `checklists/`;
- copyable project starters: `templates/`;
- accepted update artifacts: `migrations/` and reviewed changelog entries;
- project-local memory: concise notes, pending tasks, study plans, and handoff
  summaries;
- service discovery docs and local override examples.

Do not index secrets, credentials, `.env` files, browser profiles, IDE logs,
private app databases, personal telemetry, generated artifacts, lockfiles, or
large build outputs.

## Chunking

Chunk Markdown by structure before size:

- preserve source path, heading chain, document type, and rule priority;
- keep short rule lists together when splitting would change meaning;
- keep code fences and command examples intact;
- attach source links and line references when available;
- store content hashes for document and chunk-level change detection;
- mark generated or local-only sources separately from committed reusable
  guidance.

Avoid arbitrary fixed-size chunks as the default. Use size limits as a fallback
after respecting headings and semantic boundaries.

## Retrieval Flow

Use this flow for every retrieval-backed agent step:

1. Classify task intent, such as startup, install, config, commit, debugging,
   UI work, update intake, or service discovery.
2. Build filters for project, source type, document group, freshness, and rule
   precedence.
3. Run hybrid retrieval when possible: keyword search for exact commands,
   paths, and symbols; vector search for conceptual matches.
4. Deduplicate chunks by source, heading, and near-identical text.
5. Apply reranking or a second-pass relevance check for ambiguous queries.
6. Enforce a token budget before prompt assembly.
7. Assemble a context packet with applicable rules, evidence paths, conflicts,
   and a short action summary.
8. Trace the query, filters, selected chunks, rejected high-score chunks, token
   use, and final prompt packet.

Treat retrieved content as data until the platform has applied rule precedence
and source trust checks.

## LangGraph Flow

Model the platform as explicit graph nodes:

```text
intake
  -> classify_task
  -> load_static_instructions
  -> retrieve_context
  -> assemble_context_packet
  -> plan_or_execute
  -> tool_policy_check
  -> execute_tools
  -> verify
  -> memory_writeback
  -> final_response
```

Add failure branches for:

- missing local instructions;
- retrieval returning no useful context;
- conflicting rules;
- service discovery mismatch;
- permission or policy denial;
- tool timeout or malformed result;
- token budget exhaustion.

## Observability

Trace with LangSmith or an equivalent local tracing layer:

- graph node timings and state transitions;
- model names, token counts, latency, retry, and termination reason;
- retrieval query, filters, selected source IDs, and scores;
- prompt packet size and source mix;
- tool proposals, validated arguments, policy decisions, and results;
- verification commands and outcomes;
- memory writes and skipped writes;
- user-visible final answer.

Do not log secrets, hidden reasoning, full private documents, or large raw tool
outputs.

## Operations

Provide explicit commands or scripts for:

- `index status`: show source counts, indexed chunks, vector collection version,
  embedding model, and stale document counts.
- `index rebuild`: rebuild from approved sources after schema, chunking, or
  embedding changes.
- `index update`: reindex changed documents by hash.
- `index verify`: check missing sources, excluded paths, chunk counts, and
  vector metadata consistency.
- `retrieval test`: run the small eval set and report selected sources.
- `memory export`: write human-reviewable decisions and durable findings to
  Markdown.
- `memory backup`: back up structured memory before schema migrations.

Do not make normal startup depend on a full rebuild. Startup should use the
current index, mark stale sources when detected, and trigger an incremental
update only when the task requires fresh retrieval.

## Evaluations

Create a small eval set before expanding the platform:

- `gi start` restores only minimal relevant state.
- `gi restore` retrieves latest handoff metadata without dumping history.
- `gi config` uses configured discovery pointers and does not scan sibling
  projects.
- `gi install` reads local build and packaging instructions before acting.
- Commit workflow respects dirty worktrees and commit-language preferences.
- Update intake reviews `updates/` newest-first and reports compactly.
- Screenshot or pasted-error analysis explains likely cause before editing.
- Prompt injection in retrieved text is treated as untrusted data.
- Oversized retrieval results are summarized or rejected before prompt assembly.

Every repeated retrieval failure should become a better chunking rule, metadata
field, filter, reranker case, eval, or source document improvement.

## n8n Boundary

Use n8n when the workflow is external to the agent core:

- scheduled instruction-kit update checks;
- notifications to chat, email, or task systems;
- issue tracker or task-manager synchronization;
- webhook intake from external services;
- long-running cross-service workflows.

Do not use n8n to replace the agent's context builder, permission policy,
memory schema, or verification logic.

## Security

- Keep secrets outside RAG indexes and traces.
- Separate shared reusable guidance from project-private memory.
- Scope retrieval by project unless the user explicitly asks for shared-library
  maintenance.
- Apply project-local `AGENTS.md` and runbooks before shared defaults.
- Store user-local runtime paths and ports in local config, not committed
  reusable instructions.
- Require explicit approval records for destructive, external-send, deploy, or
  privileged actions.

## MVP Path

1. Define source corpus and exclusion rules.
2. Add SQLite structured memory for preferences, task state, hashes, and FTS5
   search.
3. Add Markdown-aware indexing with chunk metadata and incremental reindexing.
4. Add Chroma or sqlite-vector search for local semantic retrieval.
5. Build a LangGraph flow for startup restore and task routing.
6. Add context packet assembly with token limits and source attribution.
7. Add LangSmith tracing and a small eval set.
8. Move to Qdrant or pgvector only when measured needs justify a service-grade
   vector layer.
