# 0003: A stateless Python shim, and result.json as the contract

Status: proposed
Date: 2026-10-23

## Context

The request asks for a thin shim that turns each component into a wrangler configuration, runs a pinned wrangler and keeps no state of its own; for a plan that changes nothing; and for applies that are safe to repeat.
wrangler deploys a Worker but does not say what would change, and every `wrangler deploy` creates a new deployment, even of identical content.
The driver reads `result.json` from every plane, so its shape is a contract that other code will depend on.

## Decision

- **Python 3.13** for the shim, under the owner's Python standards (CLI archetype, agent-facing errors), with `pydantic` and `httpx` as its only runtime dependencies.
- **wrangler pinned** to an exact version in a `package.json` that holds nothing else, installed with `npm ci`, and run from `node_modules/.bin`.
- **Desired against observed.** The shim translates each component into its desired state (pure), reads the Worker from Cloudflare with read-only calls, and compares them into `create`, `update` or `unchanged` (pure). `plan` stops there; `apply` runs wrangler only for components that are not `unchanged`.
- **A deployment marker is the only record.** Each deploy carries `--message "orc project=<owner/repo> commit=<commit> config=<hash>"`, which Cloudflare keeps as the deployment's `workers/message` annotation. The project in the newest marked deployment is the Worker's owner (ADR 0001); a Worker owned by the project asking, whose active deployment carries the desired marker, with workers.dev on and previews off, is `unchanged`. Nothing is stored in the repository, a file or a state backend.
- **`result.json` version 1**: exactly `schema_version`, `components` (each exactly `name` and `url`) and `summary`. A change that removes or renames a key is a new schema version, and the driver is changed first to read both.

## Alternatives

- **A Node shim with no dependencies.** One runtime fewer, but no owner standard for its lint, types or tests.
- **A Bash shim.** The lightest, but the find-or-create logic of increment 2 is where shell goes wrong silently.
- **OpenTofu or Terraform.** Keeps state, which the request forbids, and would sit beside wrangler rather than replace it.
- **Deploy on every apply.** Simpler, but a second apply would change something, and a plan could never say "unchanged".

## Consequences

- Two runtimes on the runner (uv and Node), about a minute of set-up per run.
- A change made by hand on the dashboard that creates no deployment is not detected; the runbook says so.
- A change to the translation redeploys exactly the components whose configuration it changes, the next time each is applied.

## What enforces it

- import-linter: the pure modules (`contract`, `static_site`, `changes`) cannot import `httpx` or `subprocess`.
- AC10 and AC28 fix the shape of `result.json`; AC11 the pinned wrangler; AC15, AC20 and AC21 that a plan changes nothing and a second apply changes nothing; AC29 and AC30 that the marker's owner is honoured.
- That the shim writes no state of its own can only be reviewed.
