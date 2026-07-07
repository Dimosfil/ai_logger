# Connected Projects

Last reviewed: 2026-07-07

This register records external local repositories that are intentionally used as
architecture or implementation sources for `ai_logger`. Do not treat sibling
folders as in scope unless they are listed here or the user explicitly names
them for the current task.

## LLM Providers

- Local path: `D:\AI\llm_providers`
- Repository: `https://github.com/Dimosfil/llm_providers.git`
- Role: reusable Node.js provider boundary for LLM and local agent runtimes.
- Current ai_logger use: logic source for the Python smart log-search provider
  registry; no Node.js runtime dependency is wired.
- Source of truth: `D:\AI\llm_providers\README.md`,
  `D:\AI\llm_providers\tools\project-memory\specs\provider-architecture.md`,
  and package exports in `D:\AI\llm_providers\package.json`.
- Privacy boundary: inspect source, tests, README/docs, manifests, and compact
  project-memory specs only. Do not read secrets, local runtime config, logs,
  databases, generated artifacts, or unrelated sibling repositories.
- Update command: use that repository's own instructions before any write,
  dependency update, build, test, commit, or push.
