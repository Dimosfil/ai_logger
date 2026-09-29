# Feature Workflow Contract

Feature: TODO
Owner or source of agreement: TODO
Last updated: TODO

Portability goal: this document describes behavior independently from the
current language, framework, platform, or UI toolkit.

## Feature Idea

TODO

## User Problem

TODO

## Goal

TODO

## Functional Description

TODO

## Business Rules And Invariants

- TODO

## Actors, Roles, And Permissions

- TODO

## Non-Goals

- TODO

## User-Visible Promise

TODO

## Entry Points

- TODO

## Preconditions

- TODO

## Workflow

```mermaid
flowchart TD
    start["Start"] --> step1["TODO"]
    step1 --> decision{"TODO decision?"}
    decision -->|Yes| yesPath["TODO"]
    decision -->|No| noPath["TODO"]
    yesPath --> done["Done"]
    noPath --> done
```

## Required Order

1. TODO
2. TODO
3. TODO

## Branches And States

- TODO

## Blocking And Background Work

- Blocks user interaction: TODO
- Must not block user interaction: TODO
- Background work: TODO

## Loading And Empty States

- TODO

## Failure, Retry, And Cancellation

- TODO

## Data And Freshness Rules

- TODO

## Inputs, Outputs, And Validation

- Inputs: TODO
- Outputs: TODO
- Validation: TODO

## Observability

- User-visible errors: TODO
- Logs or metrics: TODO

## Implementation Plan

Technical approach: TODO

Likely affected areas:

- TODO

Dependencies and risks:

- TODO

Rollout or fallback:

- TODO

## Current Implementation Map

Current files, routes, commands, schemas, services, or assets that implement the
behavior:

- TODO

Implementation notes that are not part of the portable behavior contract:

- TODO

## Sprint Breakdown

### Sprint 1: TODO

Goal: TODO

Scope:

- TODO

Tasks:

- [ ] TODO

Exit criteria:

- TODO

Verification:

- TODO

## Verification

- Happy path: TODO
- Branches: TODO
- Slow or failed dependencies: TODO
- Ordering guarantees: TODO
- Regression areas: TODO

## Open Questions

- TODO
