# AI Engineering Benchmarks

Use this pattern when proving that an instruction kit, runtime layer, model
router, RAG startup flow, or memory system improves AI-assisted engineering
economics without lowering delivery quality.

Do not frame the benchmark as a claim that one assistant is smarter than
another. Prove a narrower operational claim:

```text
The optimized workflow reduces cost per completed engineering task while
preserving acceptable quality.
```

## Benchmark Claim

Define the claim before collecting data:

- Baseline workflow: raw assistant usage without project-specific summaries,
  layered instructions, model routing, memory reuse, or context filtering.
- Optimized workflow: the GI or project-local workflow using relevant
  instructions, summaries, routing, retrieval, memory, and cost controls.
- Success target: lower cost per successful task with quality signals that are
  equal to or better than the baseline.

Keep the claim specific to the measured workflow. Do not generalize from one
project, model, or task set to all AI engineering work.

## Required Metrics

Measure these fields for every benchmark task:

- Input tokens.
- Output tokens.
- Estimated or actual model cost.
- Cost per completed task.
- Retry count or number of assistant attempts.
- Completion latency.
- Quality signal, such as tests passing, endpoint working, accepted diff, fixed
  bug reproduction, reviewer approval, or no observed regression.
- Context efficiency signals, such as files opened, summaries reused, retrieved
  documents, and large files avoided.

When provider accounting exposes cached input separately, record it but do not
treat cached tokens as the main optimization target. Optimize and report total
live context size first.

## Task Set

Use identical or paired engineering tasks across both workflows. Prefer 10 to
20 tasks for a minimum viable benchmark.

Include several task types:

- Bug fixes with a reproducible failure.
- Small feature additions with tests or smoke checks.
- Repository analysis or architecture summary tasks.
- Focused refactors with clear acceptance criteria.
- Performance, query, or configuration improvements when relevant to the
  project.

Keep tasks small enough to repeat and large enough to require real context
selection. Avoid cherry-picking tasks that only benefit the optimized workflow.

## Fair Comparison Rules

- Use the same repository state, task prompt, acceptance criteria, and time
  budget for both workflows.
- Use the same model family where the benchmark is about context optimization
  rather than model quality.
- Record model differences explicitly when the optimized workflow uses routing
  across cheaper and more expensive models.
- Do not let one workflow receive hidden project knowledge unavailable to the
  other unless the benchmark is explicitly measuring memory reuse.
- Stop counting a task as successful only after the same acceptance signal is
  reached in both workflows.
- Record failures, abandoned attempts, and manual interventions instead of
  excluding them from the data.

## Workflow Variants

Use clear labels so results remain comparable:

- `raw`: ordinary assistant usage with broad manual context, no summaries, and
  no explicit cost routing.
- `gi-startup`: optimized startup and context restoration through local
  instructions and summaries.
- `gi-routing`: optimized startup plus model routing, fallback behavior, and
  budget controls.
- `gi-memory`: optimized workflow with verified project memory or previous
  handoff summaries available.

Only compare variants that answer the same benchmark question.

## Result Table

Summarize each task with compact data:

| Task | Workflow | Input Tokens | Output Tokens | Cost | Retries | Time | Quality Signal | Notes |
|---|---:|---:|---:|---:|---:|---:|---|---|
| TODO | raw | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | optimized | TODO | TODO | TODO | TODO | TODO | TODO | TODO |

Then summarize aggregate results:

| Metric | Raw Workflow | Optimized Workflow | Change |
|---|---:|---:|---:|
| Median input tokens | TODO | TODO | TODO |
| Median cost per successful task | TODO | TODO | TODO |
| Median retries | TODO | TODO | TODO |
| Median completion latency | TODO | TODO | TODO |
| Successful tasks | TODO | TODO | TODO |

Use medians for small samples so one unusually large task does not dominate the
result. Report notable outliers separately.

## Interpretation

Treat the benchmark as useful only when it includes both economy and quality:

- Strong result: lower cost per successful task, same or better quality, and
  fewer retries or lower latency.
- Mixed result: lower cost with weaker quality, lower tokens with more retries,
  or faster completion with incomplete checks.
- Weak result: token reduction without lower total cost or without a successful
  task outcome.

Prefer concrete claims such as "reduced median input tokens for these 12 tasks"
over broad claims such as "made AI engineering cheaper."

## Related Patterns

- Use `patterns/RAG_STARTUP_FLOW.md` for token-conscious context restoration.
- Use `patterns/MODEL_ROUTING_AND_COST_CONTROL.md` for routing, logging, and
  budget controls.
- Use `patterns/PROJECT_TESTING_STRATEGY.md` for task-specific quality signals.
