from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .llm import LlmProviderError
from .log_search import LogSearchMatch, rank_candidates
from .log_search_providers import create_log_search_llm_provider, normalize_log_search_provider
from .records import LogRecord


LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
DEFAULT_PROJECT = "default"


@dataclass(frozen=True)
class LogFileRef:
    project: str
    name: str
    path: Path
    size_bytes: int
    modified_timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "name": self.name,
            "size_bytes": self.size_bytes,
            "modified_timestamp": self.modified_timestamp,
        }


class WebLogRepository:
    def __init__(self, root_path: str | Path) -> None:
        self.root_path = Path(root_path)

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "WebLogRepository":
        env = environ or os.environ
        path = (
            env.get("AI_LOGGER_WEB_LOGS_ROOT")
            or env.get("AI_LOGGER_QUERY_LOGS_PATH")
            or env.get("AI_LOGGER_SERVER_PROJECT_DAILY_DIR")
            or env.get("AI_LOGGER_SERVER_JSONL_PATH")
            or "logs"
        )
        return cls(path)

    def overview(self) -> dict[str, Any]:
        files = self.list_files()
        projects: dict[str, dict[str, Any]] = {}
        for file_ref in files:
            project = projects.setdefault(
                file_ref.project,
                {"name": file_ref.project, "file_count": 0, "size_bytes": 0},
            )
            project["file_count"] += 1
            project["size_bytes"] += file_ref.size_bytes
        return {
            "root": str(self.root_path),
            "exists": self.root_path.exists(),
            "levels": list(LOG_LEVELS),
            "projects": sorted(projects.values(), key=lambda item: str(item["name"]).casefold()),
            "files": [file_ref.to_dict() for file_ref in files],
        }

    def list_files(self, project: str | None = None) -> list[LogFileRef]:
        files = [
            file_ref for file_ref in self._discover_files() if not project or file_ref.project == project
        ]
        return sorted(
            files,
            key=lambda item: (item.project.casefold(), item.modified_timestamp, item.name.casefold()),
            reverse=True,
        )

    def read_records(
        self,
        *,
        project: str | None = None,
        file_name: str | None = None,
        levels: set[str] | None = None,
        text: str | None = None,
        limit: int = 200,
    ) -> list[LogRecord]:
        selected = self._select_files(project=project, file_name=file_name)
        needle = text.casefold().strip() if text else ""
        records: list[LogRecord] = []
        for file_ref in selected:
            records.extend(_read_jsonl_records(file_ref.path, levels=levels, text=needle))
        records.sort(key=lambda record: record.timestamp)
        if limit > 0:
            return records[-limit:]
        return records

    def search(
        self,
        *,
        query: str,
        project: str | None = None,
        file_name: str | None = None,
        levels: set[str] | None = None,
        max_records: int = 500,
        top_k: int = 8,
        use_llm: bool = True,
        provider_name: str | None = None,
    ) -> dict[str, Any]:
        records = self.read_records(
            project=project,
            file_name=file_name,
            levels=levels,
            limit=max_records,
        )
        candidates = rank_candidates(query, records)
        matches = [
            LogSearchMatch(record=candidate.record, score=candidate.score)
            for candidate in candidates[:top_k]
        ]
        provider = "local"
        warnings: list[str] = []
        summary = _local_summary(query, matches)

        if use_llm and candidates:
            try:
                candidate_count = int(os.environ.get("AI_LOGGER_LOG_SEARCH_CANDIDATES", "30"))
                llm_provider = create_log_search_llm_provider(provider_name)
                if llm_provider:
                    analysis = llm_provider.analyze(
                        query,
                        candidates[: max(candidate_count, top_k)],
                        top_k=top_k,
                    )
                    provider = llm_provider.name
                    summary = analysis.summary
                    matches = _matches_from_llm(analysis.matches, candidates, top_k)
            except LlmProviderError as exc:
                warnings.append(str(exc))

        return {
            "query": query,
            "summary": summary,
            "provider": provider,
            "requested_provider": normalize_log_search_provider(provider_name),
            "warnings": warnings,
            "matches": [
                {
                    "score": match.score,
                    "reason": match.reason,
                    "record": match.record.to_dict(),
                }
                for match in matches
            ],
        }

    def _select_files(self, *, project: str | None, file_name: str | None) -> list[LogFileRef]:
        files = self.list_files(project=project)
        if file_name:
            safe_name = Path(file_name).name
            files = [file_ref for file_ref in files if file_ref.name == safe_name]
        return files

    def _discover_files(self) -> list[LogFileRef]:
        if self.root_path.is_file() and self.root_path.suffix.lower() == ".jsonl":
            return [_file_ref(DEFAULT_PROJECT, self.root_path.name, self.root_path)]
        if not self.root_path.exists() or not self.root_path.is_dir():
            return []

        refs: list[LogFileRef] = []
        for path in self.root_path.rglob("*.jsonl"):
            if not path.is_file():
                continue
            try:
                relative = path.relative_to(self.root_path)
            except ValueError:
                continue
            project = relative.parts[0] if len(relative.parts) > 1 else DEFAULT_PROJECT
            refs.append(_file_ref(project, path.name, path))
        return refs


def render_index_html() -> str:
    return INDEX_HTML


def _file_ref(project: str, name: str, path: Path) -> LogFileRef:
    stat = path.stat()
    return LogFileRef(
        project=project,
        name=name,
        path=path,
        size_bytes=stat.st_size,
        modified_timestamp=stat.st_mtime,
    )


def _read_jsonl_records(path: Path, *, levels: set[str] | None, text: str) -> list[LogRecord]:
    records: list[LogRecord] = []
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                raw = line.strip()
                if not raw:
                    continue
                if text and text not in raw.casefold():
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                record = LogRecord.from_dict(payload)
                if levels and record.level.name not in levels:
                    continue
                records.append(record)
    except OSError:
        return []
    return records


def _matches_from_llm(
    llm_matches: Iterable[tuple[str, str]],
    candidates: list[Any],
    top_k: int,
) -> list[LogSearchMatch]:
    by_id = {candidate.record.record_id: candidate for candidate in candidates}
    matches: list[LogSearchMatch] = []
    seen: set[str] = set()
    for record_id, reason in llm_matches:
        candidate = by_id.get(record_id)
        if not candidate or record_id in seen:
            continue
        seen.add(record_id)
        matches.append(LogSearchMatch(candidate.record, candidate.score, reason))
        if len(matches) >= top_k:
            return matches
    for candidate in candidates:
        if candidate.record.record_id in seen:
            continue
        matches.append(LogSearchMatch(candidate.record, candidate.score))
        if len(matches) >= top_k:
            break
    return matches


def _local_summary(query: str, matches: list[LogSearchMatch]) -> str:
    if not matches:
        return f"No local log matches found for '{query}'."
    levels = ", ".join(sorted({match.record.level.name for match in matches}))
    return f"Found {len(matches)} local match(es) for '{query}'. Levels: {levels}."


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ai_logger</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --line: #d8dde6;
      --text: #18202c;
      --muted: #647084;
      --accent: #176f70;
      --danger: #b42318;
      --warn: #9a6700;
      --info: #175cd3;
      --debug: #5d5fef;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; background: var(--bg); color: var(--text); }
    button, input, select { font: inherit; }
    .shell { display: grid; grid-template-columns: 280px minmax(0, 1fr); min-height: 100vh; }
    .sidebar { border-right: 1px solid var(--line); background: #eef1f5; padding: 18px 14px; overflow: auto; }
    .brand { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 18px; }
    .brand h1 { font-size: 20px; margin: 0; letter-spacing: 0; }
    .meta { color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }
    .main { padding: 18px; min-width: 0; }
    .toolbar { display: grid; grid-template-columns: minmax(240px, 1fr) 132px; gap: 12px; align-items: center; margin-bottom: 14px; }
    .search { display: grid; grid-template-columns: minmax(0, 1fr) 172px 96px; gap: 8px; }
    input, select { width: 100%; border: 1px solid var(--line); background: #fff; border-radius: 6px; padding: 9px 10px; color: var(--text); }
    button { border: 1px solid var(--line); background: #fff; color: var(--text); border-radius: 6px; padding: 9px 12px; cursor: pointer; }
    button.primary { border-color: var(--accent); background: var(--accent); color: #fff; }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .section-title { color: var(--muted); font-size: 12px; font-weight: 700; text-transform: uppercase; margin: 18px 4px 8px; }
    .list { display: grid; gap: 6px; }
    .list button { display: flex; align-items: center; justify-content: space-between; gap: 8px; text-align: left; padding: 9px 10px; }
    .list button.active { border-color: var(--accent); background: #e4f3f2; }
    .count { color: var(--muted); font-size: 12px; white-space: nowrap; }
    .filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; align-items: center; }
    .level { min-width: 92px; }
    .level.active { color: #fff; border-color: transparent; }
    .level.DEBUG.active { background: var(--debug); }
    .level.INFO.active { background: var(--info); }
    .level.WARNING.active { background: var(--warn); }
    .level.ERROR.active, .level.CRITICAL.active { background: var(--danger); }
    .summary { border: 1px solid var(--line); background: var(--panel); border-radius: 8px; padding: 12px; margin-bottom: 14px; display: none; }
    .summary.visible { display: block; }
    .summary strong { display: block; margin-bottom: 4px; }
    .summary .provider { color: var(--accent); }
    .layout { display: grid; grid-template-columns: minmax(0, 1fr); gap: 10px; }
    .log-table { width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; display: block; }
    .log-table thead, .log-table tbody, .log-table tr { display: table; width: 100%; table-layout: fixed; }
    .log-table tbody { display: block; max-height: calc(100vh - 220px); overflow: auto; }
    th, td { padding: 10px; border-bottom: 1px solid var(--line); vertical-align: top; text-align: left; font-size: 13px; }
    th { color: var(--muted); font-size: 12px; background: #f9fafb; position: sticky; top: 0; }
    th:nth-child(1), td:nth-child(1) { width: 164px; }
    th:nth-child(2), td:nth-child(2) { width: 92px; }
    th:nth-child(3), td:nth-child(3) { width: 190px; }
    .msg { font-weight: 650; overflow-wrap: anywhere; }
    .ctx { color: var(--muted); white-space: pre-wrap; overflow-wrap: anywhere; margin-top: 4px; }
    .pill { display: inline-block; border-radius: 999px; color: #fff; padding: 3px 8px; font-size: 12px; font-weight: 700; }
    .pill.DEBUG { background: var(--debug); }
    .pill.INFO { background: var(--info); }
    .pill.WARNING { background: var(--warn); }
    .pill.ERROR, .pill.CRITICAL { background: var(--danger); }
    .empty { padding: 26px; border: 1px dashed var(--line); border-radius: 8px; color: var(--muted); background: #fff; }
    @media (max-width: 760px) {
      .shell { grid-template-columns: 1fr; }
      .sidebar { border-right: 0; border-bottom: 1px solid var(--line); max-height: 42vh; }
      .toolbar, .search { grid-template-columns: 1fr; }
      th:nth-child(1), td:nth-child(1) { width: 120px; }
      th:nth-child(3), td:nth-child(3) { width: 120px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <h1>ai_logger</h1>
        <button id="refreshBtn" title="Refresh">Refresh</button>
      </div>
      <div id="rootMeta" class="meta"></div>
      <div class="section-title">Projects</div>
      <div id="projectList" class="list"></div>
      <div class="section-title">Log files</div>
      <div id="fileList" class="list"></div>
    </aside>
    <main class="main">
      <div class="toolbar">
        <div class="search">
          <input id="aiQuery" type="search" placeholder="Ask AI about these logs">
          <select id="providerSelect" title="LLM provider">
            <option value="">Auto provider</option>
            <option value="deepseek">DeepSeek</option>
            <option value="openai-compatible">OpenAI-compatible</option>
            <option value="mock">Mock</option>
            <option value="local">Local only</option>
          </select>
          <button id="askBtn" class="primary">Ask</button>
        </div>
        <select id="limitSelect" title="Record limit">
          <option value="100">100 rows</option>
          <option value="200" selected>200 rows</option>
          <option value="500">500 rows</option>
        </select>
      </div>
      <div id="levelFilters" class="filters"></div>
      <div id="summary" class="summary"></div>
      <div id="content" class="layout"></div>
    </main>
  </div>
  <script>
    const state = { overview: null, project: "", file: "", levels: new Set(), query: "" };
    const el = (id) => document.getElementById(id);

    async function api(path, options) {
      const response = await fetch(path, options);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || response.statusText);
      return payload;
    }

    function bytes(value) {
      if (value < 1024) return `${value} B`;
      if (value < 1048576) return `${(value / 1024).toFixed(1)} KB`;
      return `${(value / 1048576).toFixed(1)} MB`;
    }

    function html(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function selectedFiles() {
      const all = state.overview ? state.overview.files : [];
      return all.filter((item) => !state.project || item.project === state.project);
    }

    function renderSidebar() {
      el("rootMeta").textContent = state.overview.exists ? state.overview.root : `Missing: ${state.overview.root}`;
      const projects = state.overview.projects;
      el("projectList").innerHTML = "";
      const allButton = document.createElement("button");
      allButton.className = state.project === "" ? "active" : "";
      allButton.innerHTML = `<span>All projects</span><span class="count">${projects.length}</span>`;
      allButton.onclick = () => { state.project = ""; state.file = ""; render(); loadLogs(); };
      el("projectList").appendChild(allButton);
      projects.forEach((project) => {
        const button = document.createElement("button");
        button.className = state.project === project.name ? "active" : "";
        button.innerHTML = `<span>${html(project.name)}</span><span class="count">${project.file_count}</span>`;
        button.onclick = () => { state.project = project.name; state.file = ""; render(); loadLogs(); };
        el("projectList").appendChild(button);
      });

      el("fileList").innerHTML = "";
      selectedFiles().forEach((file) => {
        const button = document.createElement("button");
        button.className = state.file === file.name ? "active" : "";
        button.innerHTML = `<span>${html(file.name)}</span><span class="count">${bytes(file.size_bytes)}</span>`;
        button.onclick = () => { state.file = state.file === file.name ? "" : file.name; render(); loadLogs(); };
        el("fileList").appendChild(button);
      });
    }

    function renderLevels() {
      el("levelFilters").innerHTML = "";
      state.overview.levels.forEach((level) => {
        const button = document.createElement("button");
        button.className = `level ${level} ${state.levels.has(level) ? "active" : ""}`;
        button.textContent = level;
        button.onclick = () => {
          state.levels.has(level) ? state.levels.delete(level) : state.levels.add(level);
          render();
          loadLogs();
        };
        el("levelFilters").appendChild(button);
      });
      const clear = document.createElement("button");
      clear.textContent = "Clear";
      clear.onclick = () => { state.levels.clear(); render(); loadLogs(); };
      el("levelFilters").appendChild(clear);
    }

    function render() {
      renderSidebar();
      renderLevels();
    }

    function recordRow(item, match) {
      const context = item.context && Object.keys(item.context).length ? JSON.stringify(item.context, null, 2) : "";
      const exception = item.exception ? `\n${item.exception.type}: ${item.exception.message || ""}` : "";
      const evidence = match
        ? `<div class="ctx">score=${Number(match.score || 0).toFixed(1)}${match.reason ? ` - ${html(match.reason)}` : ""}</div>`
        : "";
      return `<tr>
        <td>${new Date(item.timestamp).toLocaleString()}</td>
        <td><span class="pill ${html(item.level)}">${html(item.level)}</span></td>
        <td>${html(item.logger)}</td>
        <td><div class="msg">${html(item.message)}</div>${evidence}<div class="ctx">${html(context + exception)}</div></td>
      </tr>`;
    }

    async function loadLogs() {
      const params = new URLSearchParams();
      if (state.project) params.set("project", state.project);
      if (state.file) params.set("file", state.file);
      if (state.levels.size) params.set("levels", Array.from(state.levels).join(","));
      params.set("limit", el("limitSelect").value);
      try {
        const payload = await api(`/api/logs?${params}`);
        el("summary").className = "summary";
        el("summary").innerHTML = "";
        renderRecords(payload.records);
      } catch (error) {
        renderError(error.message);
      }
    }

    function renderRecords(records) {
      if (!records.length) {
        el("content").innerHTML = `<div class="empty">No log records found for the current filters.</div>`;
        return;
      }
      el("content").innerHTML = `<table class="log-table">
        <thead><tr><th>Time</th><th>Level</th><th>Logger</th><th>Message</th></tr></thead>
        <tbody>${records.map(recordRow).join("")}</tbody>
      </table>`;
    }

    function renderSearchMatches(matches) {
      if (!matches.length) {
        el("content").innerHTML = `<div class="empty">No search matches found.</div>`;
        return;
      }
      el("content").innerHTML = `<table class="log-table">
        <thead><tr><th>Time</th><th>Level</th><th>Logger</th><th>Message</th></tr></thead>
        <tbody>${matches.map((match) => recordRow(match.record, match)).join("")}</tbody>
      </table>`;
    }

    async function askAi() {
      const query = el("aiQuery").value.trim();
      if (!query) return;
      el("askBtn").disabled = true;
      el("askBtn").textContent = "Asking";
      try {
        const payload = await api("/api/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query,
            project: state.project || null,
            file: state.file || null,
            levels: Array.from(state.levels),
            max_records: Number(el("limitSelect").value),
            top_k: 8,
            provider: el("providerSelect").value || null
          })
        });
        el("summary").className = "summary visible";
        const warning = payload.warnings.length ? `<div class="meta">${html(payload.warnings.join("; "))}</div>` : "";
        el("summary").innerHTML = `<strong><span class="provider">${html(payload.provider)}</span> analysis</strong><div>${html(payload.summary)}</div>${warning}`;
        renderSearchMatches(payload.matches);
      } catch (error) {
        renderError(error.message);
      } finally {
        el("askBtn").disabled = false;
        el("askBtn").textContent = "Ask";
      }
    }

    function renderError(message) {
      el("content").innerHTML = `<div class="empty">${html(message)}</div>`;
    }

    async function loadOverview() {
      try {
        state.overview = await api("/api/overview");
        render();
        await loadLogs();
      } catch (error) {
        renderError(error.message);
      }
    }

    el("refreshBtn").onclick = loadOverview;
    el("askBtn").onclick = askAi;
    el("aiQuery").addEventListener("keydown", (event) => { if (event.key === "Enter") askAi(); });
    el("limitSelect").onchange = loadLogs;
    loadOverview();
  </script>
</body>
</html>
"""
