# Agent Experience SQLite

Use SQLite as a local memory/index for the AI agent, not as the product
database and not as part of the application runtime.

## Purpose

The agent memory database stores verified project experience that helps future
sessions avoid rediscovery:

- indexed files and searchable text snippets
- symbols, routes, assets, config keys, or domain-specific references
- architectural findings
- debugging findings
- recurring failures and fixes
- useful commands and their observed results
- durable notes with evidence paths
- reusable agent experience that may improve the shared `gi` instruction kit

## Location

Recommended location:

```text
tools/project-memory/project_memory.sqlite
```

The SQLite file is usually local/generated and should be ignored by git when it
is large or rebuildable.

Commit reviewable assets instead:

- `tools/project-memory/README.md`
- `tools/project-memory/STUDY_PLAN.md`
- `tools/project-memory/NOTES.md`
- schema or indexing scripts, for example
  `tools/project-memory/build_project_memory_index.py`
- optional exported Markdown notes

## Rules

- Do not confuse agent memory SQLite with the project's application database.
- Do not store secrets, tokens, credentials, private user data, or production
  data in agent memory.
- Store verified facts, not loose guesses. Mark uncertain findings clearly.
- Include evidence paths for durable notes.
- Rebuild generated index tables from source files when possible.
- Keep human-reviewable durable knowledge exportable to Markdown.
- Do not dump the SQLite database or large query results into chat. Use targeted
  SQL queries with `LIMIT`.
- On startup, query only what is relevant to the task; do not load the whole
  database into context.
- Treat SQLite as a navigator, not as a substitute for source verification.
  Before changing behavior, open the current source files because indexed facts
  may be stale after rebuilds, refactors, or generated-asset updates.
- When a finding is reusable beyond the current project, export a concise
  recommendation to the shared instruction update intake or to a local
  `tools/project-memory/instruction-updates/` fallback. Do not treat SQLite
  memory itself as accepted shared guidance.

## Suggested Tables

Generated index tables depend on the project. Common options:

- `files`: path, extension, size, hash, modified time, indexed time, optional
  content or excerpt.
- `symbols`: path, line, kind, name, namespace/module.
- `references`: source path, line, target id/path, relationship type.
- `commands`: command, purpose, last_result, updated time.
- `failures`: symptom, cause, fix, evidence paths.
- `notes`: created time, topic, title, body, evidence paths.
- `instruction_updates`: created time, topic, problem, recommendation,
  evidence paths, privacy review, exported target, status.

Use FTS5 search tables when available, but keep a fallback query path for local
SQLite builds without FTS5.

For projects with deterministic asset or dependency graphs, add tables that
capture exact relationships rather than relying on semantic search. Examples:
Unity `.meta` GUID to asset path mappings, prefab/scene/material/script
references, assembly-definition dependencies, generated identifiers, route
graphs, or module ownership maps. Include reverse references so the agent can
answer "what uses this?" and "what will this change affect?" with evidence.

Use a vector database only as a second layer for conceptual lookup across
curated notes, summaries, architecture documents, and selected code chunks. Keep
exact identifiers, paths, GUIDs, references, and dependency edges in SQLite or
another structured store where queries are deterministic.

Keep code/source memory and specification memory logically separated. Code
memory indexes current implementation facts such as files, symbols, commands,
schemas, errors, and dependency edges. Specification memory indexes product
behavior, business rules, feature algorithms, workflow contracts, architecture
migrations, and verification guarantees. Small projects may keep both logical
layers in one SQLite database with source metadata; larger projects should split
them into separate databases, schemas, or source groups.

## Suggested CLI

Provide one small script, for example:

```powershell
python .\tools\project-memory\build_project_memory_index.py rebuild
python .\tools\project-memory\build_project_memory_index.py stats
python .\tools\project-memory\build_project_memory_index.py search "SomeSymbol"
python .\tools\project-memory\build_project_memory_index.py note "topic" "title" "body" --evidence "path/to/file"
python .\tools\project-memory\build_project_memory_index.py notes
python .\tools\project-memory\build_project_memory_index.py export-notes
```

## Markdown Export

SQLite is efficient for search, but Markdown is better for review.

Use two memory layers:

- Markdown is the human-reviewable layer. Keep it concise: handoff summaries,
  decisions, architecture notes, and curated exports.
- SQLite is the searchable agent-memory layer. Use it for detailed findings,
  file/symbol indexes, references, commands, failures, and evidence-backed
  notes.

Do not blindly migrate all Markdown into SQLite. When Markdown notes, summaries,
or architecture files become too large to read cheaply, introduce or rebuild the
SQLite memory/index and keep Markdown as the concise reviewable export.

Export durable notes to:

```text
tools/project-memory/NOTES.md
```

The export should say that SQLite is the local generated index and Markdown is
the reviewable long-lived memory.

Export reusable instruction recommendations as small Markdown files, not as raw
database dumps. Use the dated filename pattern:

```text
YYYY-MM-DD_HH-mm-ss_AGENT_RECOMMENDED_GENERAL_INSTRUCTIONS_UPDATES.md
```

## Startup Use

At the start of a task:

1. Read `AGENTS.md` and the latest handoff summary.
2. Use targeted memory search only if the task needs prior knowledge.
3. Query by symbol, path, topic, error, or feature name.
4. Read small results with evidence paths.
5. Open only the exact source files needed for the task.

Do not use SQLite memory as an excuse to load more context than the task needs.
