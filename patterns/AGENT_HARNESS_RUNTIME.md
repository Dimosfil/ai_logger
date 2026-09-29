# Agent Harness Runtime

Use this pattern when a project builds, audits, or maintains an agentic runtime:
an application where a model can plan, call tools, use connectors, update
state, or perform work across turns.

## Core Rule

The model proposes actions. The harness validates, authorizes, executes,
records, summarizes, and returns observations.

Do not rely on prompt text for safety that must be enforced by code.

## Harness Boundary

Keep these responsibilities outside the model:

- tool schema validation;
- permission and approval decisions;
- sandbox and filesystem boundaries;
- secret handling;
- budget enforcement for steps, time, tokens, cost, and tool calls;
- durable state for plans, approvals, todos, artifacts, and checkpoints;
- observability, traces, metrics, and audit records.

The model may choose, explain, draft, rank, summarize, or request actions, but
the application decides what is executable.

## Minimal Loop

Use a simple model-tool-observation loop before adding orchestration:

```text
user/task
  -> instruction and context builder
  -> model call
  -> tool or action proposal
  -> schema validation
  -> permission decision
  -> execution or approval pause
  -> structured observation
  -> context/state update
  -> repeat within budget or finish
```

Every tool call must receive a tool result, including denial, validation error,
timeout, cancellation, or failure.

## Tool Design

Prefer narrow typed tools over broad generic tools.

- Use action-specific names such as `draft_customer_email`,
  `read_account_summary`, or `request_deploy_approval`.
- Avoid broad names such as `execute_anything`, `send_message`, `run_command`,
  or `write_database` unless wrapped by strict policy and approval gates.
- Return structured results with status, data, limits, warnings, and source
  references.
- Keep tool results bounded. Summarize or page large outputs.
- Label untrusted data from webpages, emails, tickets, PDFs, logs, and
  connectors as data, not instructions.

## Risk And Permissions

Classify tools by risk before exposing them to the model:

- read-only public data;
- read-only private data;
- internal draft or analysis;
- internal write;
- external communication;
- financial, legal, healthcare, security, privileged, destructive, or deploy
  action.

Separate draft from commit for high-risk side effects. External sends,
financial operations, destructive actions, privileged access, deploys, and
regulated-domain actions need a runtime approval record outside the prompt.

## Context And Memory

Build context deliberately instead of dumping everything into the prompt.

- Load stable instructions first and volatile task state later.
- Retrieve only task-relevant files, memory, and connector data.
- Store active plans, todos, approvals, artifacts, and checkpoints outside chat
  history.
- Treat auto-compaction as state rehydration, not prose summarization.
- Preserve active objective, loaded instructions, approval state, changed files,
  validation results, blockers, and next step across compaction.

## Planning And Goals

Use planning mode for ambiguous, risky, broad, or multi-step work. In planning
mode, the agent reads, asks, and proposes; it does not perform irreversible
actions until the required approval is recorded.

Use goal-like loops only for a single objective with:

- a measurable done condition;
- step, time, token, cost, and tool-call budgets;
- checkpoints;
- validation;
- stop rules.

Do not use a goal loop for a vague backlog.

## Skills And Connectors

Expose capabilities progressively:

- discover names and descriptions first;
- load detailed skill or connector instructions only when relevant;
- attach only the connectors needed for the current task;
- namespace connector tools clearly;
- enforce authorization in the harness, not only through connector descriptions.

Do not make a consuming project depend on a shared instruction repository at
runtime unless the user explicitly asks for that.

## Observability And Evals

Trace operational events without exposing hidden reasoning:

- model request and response metadata;
- tool proposal and validated arguments;
- permission decision;
- approval record;
- execution result;
- token, cost, latency, retry, timeout, and termination reason;
- final answer or artifact.

Before launch, evaluate at least:

- normal task success;
- malformed tool arguments;
- denied permissions;
- prompt injection in retrieved or connector-provided content;
- missing, partial, or oversized tool results;
- timeout and budget exhaustion;
- compaction and resume behavior;
- approval-required side effects.

Repeated failures should become validators, narrower tools, clearer docs,
evals, or runtime policies, not only more prompt advice.

## MVP Rule

Start with the smallest useful single-agent harness. Add subagents, long-running
goal workers, broader autonomy, or more connectors only after measured failures
show that the simple harness is insufficient.
