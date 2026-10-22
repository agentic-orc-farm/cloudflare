---
title: The Cloudflare plane for agentic-orc-farm
size: large
acceptance_tests: tests/acceptance/
criteria: []   # written in the design pass, for the option chosen
---

# The Cloudflare plane for agentic-orc-farm

The request fixes the contract: one `deploy` workflow (`workflow_dispatch`, inputs `project`, `commit`, `env`, `mode`, `components`), one kind (`static-site`: a Worker with static assets, Access in front of dev and staging, prod public), a stateless shim that writes a wrangler configuration and runs a pinned wrangler, `result.json` uploaded as a run artefact, safe repeat applies, a README and a cleanup runbook.
The options below differ only in what the request leaves open: the shim's language, how Access is set up, and how the workflow reads another repository's artefacts.

## Facts every option rests on

Checked on 2026-10-23.

- **wrangler** is 4.152.0 and needs Node 22 or later, so every option has Node on the runner.
- **wrangler does not manage Access.** The one-click "Enable Cloudflare Access" for `workers.dev` (changelog, 2025-10-03) is dashboard-only, with no API or wrangler option named.
  So in every option the shim calls the Cloudflare Access API itself: it finds or creates one self-hosted Access application per dev or staging hostname, and attaches one reusable policy that admits the read-only service token.
  It finds things by name or hostname, never by a stored id, so it keeps no state.
- **Preview URLs** bypass the `workers.dev` hostname's Access application. Since wrangler 4.34 they default to off; the shim sets `preview_urls = false` explicitly so a later default cannot reopen them.
- **`actions/download-artifact`** (v8.0.2) accepts `repository`, `run-id` and `github-token`, so reading another repository's artefact needs only a token that can read that repository's Actions.
  The plane's own `GITHUB_TOKEN` cannot read another private repository.
- **Concurrency:** two applies racing for the same project and environment could both create an Access application. Every option uses a workflow `concurrency` group keyed on project and environment, which is what makes "never duplicates" hold, not luck.

## Options

### Option A: a Python shim (recommended)

A small Python 3.13 package, `uv`-managed, following `PYTHON-BASE.md` and the agent-facing part of `PYTHON-CLI.md`.
It parses `components` into frozen models, writes one `wrangler.jsonc` per component, calls the Access API, runs wrangler in a subprocess with a timeout, and writes `result.json`.
wrangler is pinned in a `package.json` and `package-lock.json` that hold nothing else, installed with `npm ci`.

- **Cost:** two runtimes on the runner (uv and Node), about one minute of set-up per run. The owner's CI baseline (ruff, pyright, pytest, pip-audit) comes for free from the scaffold.
- **Risk:** low. The translation is pure functions, tested locally with no credentials; the Cloudflare and GitHub calls sit behind one module each, faked in unit tests and exercised for real only in this repository's CI.
- **Standards:** follows `PYTHON-BASE.md`, `PYTHON-CLI.md` (agent-facing errors, idempotency, `--json`) and `GITHUB.md` (pinned actions, least-privilege permissions, secrets only in the job that needs them, build once and promote).

### Option B: a Node shim, no dependencies

The same shape in plain JavaScript (ES modules, `node:test`, global `fetch`), with wrangler as its only dependency.

- **Cost:** one runtime instead of two; slightly faster runs.
- **Risk:** low technically, but the owner has no JavaScript standard outside `UI.md`, so lint, types and test rules would be invented for this repository, and reviewed by eye.
- **Standards:** departs from the owner's Python default for tools. The saving (one fewer runtime set-up step) is small next to losing the checked standard.

### Option C: a Bash shim with `jq` and `curl`

- **Cost:** the lightest: no package, no lock file beyond wrangler's.
- **Risk:** high. Access is find-or-create-or-update logic with pagination and error handling, which is where shell scripts go wrong silently; local tests of the translation would need `bats` and would be weak.
- **Standards:** no standard covers shell tools; it fails the spirit of "tested over theoretical" in `PYTHON-BASE.md`.

### Rejected outright: Terraform or OpenTofu for the Worker and Access

It keeps state, which the request forbids, and it would sit beside wrangler rather than replace it.

## How the workflow reads another repository's artefacts

This is a sub-choice that applies to whichever option above is picked.

1. **A GitHub App owned by the organisation (recommended).**
   Installed on the organisation's repositories with only `Actions: read` and `Metadata: read`.
   The plane holds the App id and private key as its own secrets, and `actions/create-github-app-token` mints a token scoped to the one project repository, which expires within an hour.
   With it the workflow finds the successful CI run for `commit` (`GET /repos/{project}/actions/runs?head_sha=...`), checks it has an artefact named for each component, and downloads it with `actions/download-artifact`.
   Cost: creating and installing the App once, by the owner. Nothing to rotate yearly, and no person's account behind it.
2. **A fine-grained personal access token** with `Actions: read` on the organisation's repositories.
   Simpler to create, but long-lived, tied to a person, and it has to be rotated when it expires.
3. **Projects publish the artefact somewhere the plane reads** (a release, a bucket).
   Changes every project's CI and the contract; rejected.
4. **The plane's own `GITHUB_TOKEN`**, which works only if every project repository is public, and I could not verify that it can download artefacts from other public repositories.
   Rejected as fragile: one private project breaks it.

Two limits hold whichever is picked, and the design will state them in the README: artefacts expire with the project's retention setting (90 days by default), so promoting an older commit fails with a clear message; and if several runs for the commit carry the artefact, the plane takes the most recent successful one.

## Recommendation

Option A with a GitHub App.
Python follows the owner's checked standard at the cost of one extra runtime set-up step, and the App gives short-lived, repository-scoped, read-only tokens that belong to the organisation rather than to a person.

The request is too big for one pull request.
The design pass will split it, with the first increment the barest end-to-end thing: plan and apply of a public (prod) static site from a fixture project's artefact, reporting its address in `result.json`.
Access for dev and staging, the README and the cleanup runbook would follow.

## Questions for the design pass

- **Hostnames.** `workers.dev` (`<worker>.<account-subdomain>.workers.dev`) needs no zone and is what I would use. A custom domain needs a zone the request does not name. I assume `workers.dev`.
- **Who else passes Access.** The request names only the service token. The owner will probably want to open dev and staging in a browser, which needs an email rule and a login method (one-time PIN is the lightest). I would ask before adding it.
- **Worker names.** Workers names are limited to 63 characters, lowercase letters, digits and dashes. I would use `<repo>-<env>` and refuse names that do not fit, rather than truncate and risk two projects sharing a Worker.
