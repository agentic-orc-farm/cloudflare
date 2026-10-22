---
title: The Cloudflare plane for agentic-orc-farm
size: large
acceptance_tests: tests/acceptance/
criteria:
  # Increment 1 only. Offline: no credentials, no network. PLANE_ORG=agentic-orc-farm in the environment.
  - id: AC1
    kind: new
    text: "The repository has `.github/workflows/deploy.yml`, named `deploy`, started only by `workflow_dispatch`, with exactly the required inputs `project`, `commit`, `env` (a choice of dev, staging and prod), `mode` (a choice of plan and apply) and `components`."
  - id: AC2
    kind: new
    text: "The deploy workflow uploads `result.json` as a run artefact named `result`, in a step with `if: always()`, so it is uploaded even when an earlier step failed."
  - id: AC3
    kind: new
    text: "The deploy workflow has a `concurrency` group built from the `project` and `env` inputs, with `cancel-in-progress` false."
  - id: AC4
    kind: new
    text: "No `run:` block in any file under `.github/workflows/` contains `${{ inputs.` or `${{ github.event.inputs.`; inputs reach commands only through `env:`."
  - id: AC5
    kind: new
    text: "With no credentials in the environment, `uv run cf-plane wrangler-config --project agentic-orc-farm/example --env prod --component '{\"name\":\"site\",\"kind\":\"static-site\",\"plane\":\"cloudflare\",\"artefact\":\"site\"}' --assets DIR` exits 0 and prints JSON whose `name` is `example-site-prod`, `workers_dev` is true, `preview_urls` is false, `assets.directory` is DIR and `assets.not_found_handling` is `404-page`, with no `main` key."
  - id: AC6
    kind: new
    text: "With no credentials in the environment, `uv run cf-plane deploy` given a component whose kind is not `static-site` exits non-zero and writes a `result.json` whose `components` is empty and whose `summary` names the unknown kind and names `static-site` as the kind offered."
  - id: AC7
    kind: new
    text: "With no credentials in the environment, `uv run cf-plane deploy` with `--env dev` or `--env staging` exits non-zero and writes a `result.json` whose `components` is empty and whose `summary` says private environments are not offered yet."
  - id: AC8
    kind: new
    text: "With no credentials in the environment, `uv run cf-plane deploy` exits non-zero and writes a `result.json` with empty `components` and a `summary` that names the input at fault, for each of these inputs - a commit that is not 40 lowercase hexadecimal characters; a project outside the organisation named in `PLANE_ORG`; a project whose repository name has characters other than lowercase letters, digits and dashes; a component whose plane is not `cloudflare`; two components with the same name; and `components` that is not a non-empty JSON list of objects with exactly the keys name, kind, plane and artefact."
  - id: AC9
    kind: new
    text: "With no credentials in the environment, `uv run cf-plane deploy` for a component whose Worker name (`<repo>-<component>-<env>`) would be longer than 63 characters exits non-zero and writes a `result.json` whose `summary` contains that Worker name and the number 63."
  - id: AC10
    kind: new
    text: "Every `result.json` that `cf-plane deploy` writes, for a plan, an apply or a refusal, is a JSON object with exactly the keys `schema_version` (the integer 1), `components` (a list of objects with exactly the keys `name` and `url`) and `summary` (a string of at most 1000 characters)."
  - id: AC11
    kind: new
    text: "`package.json` pins `wrangler` to an exact version (digits and dots only, no range), and `package-lock.json` records the same version for `node_modules/wrangler`."
  - id: AC12
    kind: new
    text: "`make test` exits 0 with CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID and GITHUB_READ_TOKEN removed from its environment."
  - id: AC13
    kind: new
    text: "README.md has a `## Kinds` section that lists `static-site`, and names the repository secrets CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID and PLANE_READER_PRIVATE_KEY and the repository variable PLANE_READER_CLIENT_ID."
  - id: AC14
    kind: new
    text: "`docs/cleanup.md` has a `## static-site` section."
  # Live: in this repository's CI, with its own token, against the fixture project and commit (ACCEPTANCE_PROJECT, ACCEPTANCE_COMMIT); <repo> is ACCEPTANCE_PROJECT's repository name and <subdomain> the account's workers.dev subdomain.
  - id: AC15
    kind: new
    text: "A plan to prod for a component named `plan-only` (kind static-site, artefact fixture-site) exits 0, lists `plan-only` with the url `https://<repo>-plan-only-prod.<subdomain>.workers.dev`, has the line `plan-only: would create Worker <repo>-plan-only-prod` in its summary, and afterwards the account has no Worker named `<repo>-plan-only-prod`."
  - id: AC16
    kind: new
    text: "A plan to prod for a component `site` with GITHUB_READ_TOKEN unset, for a commit with no artefacts (forty zeros), exits 0 and lists `site` with the url `https://<repo>-site-prod.<subdomain>.workers.dev`."
  - id: AC17
    kind: new
    text: "An apply to prod of a component `site` with artefact `fixture-site` for the fixture commit exits 0 and lists `site` with the url `https://<repo>-site-prod.<subdomain>.workers.dev`, and within 120 seconds a GET of `<url>/commit.txt` returns 200 with the fixture commit as its body."
  - id: AC18
    kind: new
    text: "After that apply, a GET of `<url>/no-such-page` returns 404 with the body of the fixture's `404.html`."
  - id: AC19
    kind: new
    text: "After that apply, Cloudflare's script subdomain API reports `enabled` true and `previews_enabled` false for the Worker `<repo>-site-prod`."
  - id: AC20
    kind: new
    text: "A second apply with the same inputs exits 0, lists the same url, has the line `site: unchanged` in its summary, and leaves the Worker's active deployment id as it was after the first apply."
  - id: AC21
    kind: new
    text: "A plan with the same inputs after the apply exits 0, has the line `site: unchanged` in its summary, and leaves the Worker's active deployment id as it was."
  - id: AC22
    kind: new
    text: "An apply of `site` for a commit with no `fixture-site` artefact (forty zeros) exits non-zero, its summary contains `fixture-site` and that commit, and the Worker's active deployment id does not change."
---

# The Cloudflare plane for agentic-orc-farm

The request fixes the contract: one `deploy` workflow (`workflow_dispatch`, inputs `project`, `commit`, `env`, `mode`, `components`), one kind (`static-site`: a Worker with static assets, Access in front of dev and staging, prod public), a stateless shim that writes a wrangler configuration and runs a pinned wrangler, `result.json` uploaded as a run artefact, safe repeat applies, a README and a cleanup runbook.
The options below differ only in what the request leaves open: the shim's language, how Access is set up, and how the workflow reads another repository's artefacts.

## Facts every option rests on

Checked on 2026-10-23.

- **wrangler** is 4.152.0 and needs Node 22 or later, so every option has Node on the runner.
- **wrangler does not manage Access.** The one-click "Enable Cloudflare Access" for `workers.dev` (changelog, 2025-10-03) is dashboard-only, with no API or wrangler option named.
  (Corrected in the design pass: Cloudflare's Workers documentation now also describes Access applications with a `worker` destination, created through the API; increment 2 chooses between that and a hostname application.)
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

# Design

Chosen: Option A, a Python shim, with an organisation-owned, read-only GitHub App for reading project artefacts.
The reason given: Python follows the owner's checked standards and CI baseline and keeps the find-or-create logic in pure, locally tested functions; the App gives short-lived, read-only tokens scoped to one repository that belong to the organisation rather than a person.

The questions the options pass left open had no answers, so this design takes the narrow reading of each and says so:

- **Hostnames:** `workers.dev` only (`https://<worker>.<account subdomain>.workers.dev`). No zone or custom domain: a domain for prod waits for a request that names one (the orchestrator's ADR 0012 lists it as owner set-up "if prod needs one").
- **Who passes Access:** only the read-only service token, as the request says. A browser login for the owner is a small later change (one more policy), and is not designed here.
- **Worker names:** `<repo>-<component>-<env>`, refused rather than truncated when they do not fit (this repository's ADR 0001). The request says "named after the project and environment"; the component name is added because `deploy.yaml` may list several static sites, and without it two components of one project would deploy over each other.

## Increments

The request is too big for one pull request to review well, and the Access logic is the part most likely to go wrong, so it gets its own.

1. **This pull request: the whole pipeline for a public environment.**
   The `deploy` workflow, the shim, `plan` and `apply` of `static-site` to `prod`, reading the artefact through the App, `result.json`, safe repeat applies, the README and the runbook's `static-site` section.
   `dev` and `staging` are refused with a clear message until increment 2, so nothing private is ever deployed in public.
   Validated end to end in this repository's CI: a real plan and a real apply of a fixture site, read from a real artefact, served from a real address.
2. **Next pull request: Access in front of dev and staging.**
   Find the organisation's service token by name; find or create one reusable Service Auth policy that admits it; find or create one Access application per private Worker, created before the Worker is first reachable; refuse when two applications match.
   Cloudflare's docs now offer an Access application with a `worker` destination as well as a hostname application; that design pass chooses between them (the `worker` destination needs the Worker to exist first, so the order of creation decides it).
   It adds the `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET` section to the README, the Access section to the runbook, and its own criteria: without the headers a private address does not return 200, with them it does, and a second apply leaves exactly one application and one policy.
   Increment 2 is a new request through the flow; its criteria replace AC7.

The plane serves no project until increment 2 merges, because every project's first deploy is to dev.

## The smallest version

One command, `cf-plane deploy`, run by one workflow, does this for each component in input order:

1. **Validate** every input before reading any credential (`cf-plane validate` runs the same checks on its own, so the workflow can stop early and still write `result.json`).
2. **Translate** the component into its desired state: Worker name, wrangler configuration, address, and a deployment marker (below). Pure.
3. **Observe** the Worker on Cloudflare with read-only calls: does it exist, the marker on its active deployment, its workers.dev and preview settings.
4. **Compare** desired with observed into one change per component: `create`, `update` or `unchanged`. Pure.
5. In `plan` mode, stop: report the changes and the addresses.
   In `apply` mode, for each component that is not `unchanged`, download and unpack its artefact, write `wrangler.json`, and run the pinned wrangler.
6. **Write `result.json`** and exit 0, or exit 1 with the reason on stderr and in the summary.

It keeps nothing between runs: Cloudflare is the record of what exists, and the marker on the active deployment is the record of what is running.

### The deployment marker

`wrangler deploy --message "orc commit=<commit> config=<hash>"`, where `<hash>` is the first 12 hex digits of the SHA-256 of the canonical JSON of the wrangler configuration without the assets folder's path.
A component is `unchanged` when its Worker exists, its active deployment carries exactly that marker, workers.dev is on and previews are off.
So a second apply runs no wrangler, a plan after an apply says `unchanged`, and a change to the plane's translation redeploys exactly the components it affects.
A change made by hand on the dashboard that does not create a deployment (for example a variable) is not seen; the runbook says so.

### Inputs and refusals

| Input | Rule |
|---|---|
| `project` | `<org>/<repo>`, where `<org>` equals `PLANE_ORG` (the workflow sets it from `github.repository_owner`) and `<repo>` matches `[a-z0-9-]+`. Other characters are refused, not rewritten: rewriting `my.site` and `my-site` to one name would make two projects share a Worker. |
| `commit` | 40 lowercase hexadecimal characters. |
| `env` | `prod` in increment 1; `dev` and `staging` are refused with "private environments are not offered yet". |
| `mode` | `plan` or `apply`. |
| `components` | A non-empty JSON list; each item has exactly `name`, `kind`, `plane` and `artefact`, each matching `[a-z0-9][a-z0-9-]{0,62}` (as the driver's `deploy.yaml` check does); `plane` is `cloudflare`; `kind` is one the plane offers (`static-site`); names are unique; each Worker name is at most 63 characters. |

A refusal names the input, says what is wrong and what would satisfy it, and is safe to paste into a prompt (`PYTHON-CLI.md` section 2).
Validation reads no environment variable except `PLANE_ORG`, so every refusal above happens with no credentials present.

### `result.json`, schema version 1

```json
{
  "schema_version": 1,
  "components": [{"name": "site", "url": "https://example-site-prod.acme.workers.dev"}],
  "summary": "prod plan for agentic-orc-farm/example at <commit>\nsite: would create Worker example-site-prod"
}
```

- Exactly these three keys; `components` items have exactly `name` and `url`; `summary` is at most 1000 characters.
- `url` is computed (`https://<worker>.<subdomain>.workers.dev`), not parsed from wrangler's output, so a plan gives the address an apply will produce.
- The summary's first line says the env, mode, project and commit; then one line per component: `<name>: would create Worker <worker>`, `would update Worker <worker>`, `unchanged`, `created Worker <worker>` or `updated Worker <worker>`.
- On a refusal, `components` is empty and the summary is the refusal.
- On a failure part way through an apply, `components` lists the components that are live at the new marker, the summary says which component failed and why, and the run fails. Running the same apply again finishes the job.
- The run's conclusion (success or failure) is the driver's signal; `result.json` is the detail.

### Reading the artefact

Only `apply` reads artefacts, so a plan works for a commit whose CI has not packaged anything yet, which is the case at the design gate.

- The workflow mints an installation token from the plane's GitHub App (ADR 0002) with `actions/create-github-app-token`, scoped to the one project repository and to `permission-actions: read`, and passes it to the shim as `GITHUB_READ_TOKEN`.
- The shim lists the project's artefacts with that component's `artefact` name (`GET /repos/{project}/actions/artifacts?name=<artefact>`, paginated), keeps those whose `workflow_run.head_sha` is the commit and that have not expired, and takes the newest.
  It does not require the CI run to have finished or passed: the driver asks for a deploy only after CI is green, and not waiting lets this repository's own CI test the real path against an artefact uploaded earlier in the same run.
- None found: refuse, naming the artefact and the commit, and saying that artefacts expire with the project's retention setting (90 days by default) and that the project's CI must upload it.
- It downloads the zip (`GET .../artifacts/{id}/zip`, which redirects to storage; the Authorization header is not sent across the redirect) and unpacks it into a fresh temporary folder, refusing absolute paths, `..`, symlinks, more than 20,000 files or more than 500 MB unpacked, and naming the rule that refused.
  20,000 is the Workers Free plan's asset file limit; wrangler itself refuses a single file over 25 MiB.

### The static-site translation

```json
{
  "name": "<repo>-<component>-<env>",
  "compatibility_date": "<a fixed date in the shim, changed deliberately>",
  "workers_dev": true,
  "preview_urls": false,
  "assets": {"directory": "<unpacked artefact>", "not_found_handling": "404-page"}
}
```

- Assets only, no `main`: the artefact is served as it is, with no code of the plane's.
- `preview_urls` is set explicitly so a later default in wrangler cannot reopen previews.
- `not_found_handling: "404-page"` serves the nearest `404.html` with status 404, which is what the owner's static-site baseline asks for (`UI.md`, a real 404); an artefact without one gets Cloudflare's plain 404.
- `cf-plane wrangler-config` prints this for a component, with no credentials and no network (AC5); it is the local, credential-free view of the translation the request asks for.

### Commands

Declared as data in `cli.py`, as `PYTHON-CLI.md` section 4 asks:

| Command | Does | Needs |
|---|---|---|
| `cf-plane validate --project --commit --env --mode --components --result PATH` | Checks the inputs; prints the repository name on success; writes `result.json` and exits 1 on a refusal. | `PLANE_ORG` |
| `cf-plane deploy` (same arguments) | Everything above. | `PLANE_ORG`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`; `GITHUB_READ_TOKEN` for `apply` only |
| `cf-plane wrangler-config --project --env --component JSON --assets DIR` | Prints one component's wrangler configuration. | Nothing |

### Layout and layering

```
src/cf_plane/
  contract.py      inputs, components and result.json as frozen pydantic models       pure
  static_site.py   the kind: Worker name, address, wrangler configuration, marker     pure
  changes.py       desired against observed, into create, update or unchanged; the summary   pure
  cloudflare.py    the Cloudflare API: account subdomain, Worker, active deployment, subdomain settings
  artefacts.py     find, download and safely unpack a project's artefact
  wrangler.py      write wrangler.json, run node_modules/.bin/wrangler
  cli.py           the commands, and writing result.json
```

- An import-linter contract: `cli` above `cloudflare | artefacts | wrangler` above `changes` above `static_site` above `contract`; and `contract`, `static_site` and `changes` may not import `httpx` or `subprocess`.
- Kinds are a dict in `changes.py` (`{"static-site": static_site}`); there is no plugin mechanism until a second kind exists.
- Every call has a timeout: 30 seconds per HTTP request, 120 seconds for an artefact download, 300 seconds for wrangler, run in its own process group and killed as a group (`PYTHON-BASE.md` section 6).
- No automatic retries: an apply is safe to run again, so the retry is running the workflow again.
- wrangler runs with `WRANGLER_SEND_METRICS=false`, and with `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` from the environment; the shim never logs either, nor `GITHUB_READ_TOKEN`.
- Before each outside effect the shim logs what it is about to do, and after it what happened (`PYTHON-CLI.md` section 3), to the Actions log; there is no journal because the plane keeps no state.

## The workflows

### `deploy` (`.github/workflows/deploy.yml`)

- `on: workflow_dispatch` with the five required string or choice inputs and nothing else; `run-name` shows mode, project, env and commit, so the driver and the owner can find a run.
- `permissions: contents: read`. The deploy token reaches only the steps that call the shim.
- `concurrency: group: deploy-${{ inputs.project }}-${{ inputs.env }}`, `cancel-in-progress: false`, so two applies for one project and env never overlap.
  GitHub keeps only one pending run per group and cancels an older pending one when a third arrives; the driver must treat a cancelled run as "ask again". (From GitHub's documented behaviour; not tested here.)
- `timeout-minutes: 15`.
- Steps: checkout; set up uv and Node; `make setup`; `cf-plane validate` (its output is the repository name); for `apply` only, mint the App token for that repository; `cf-plane deploy`; upload `result.json` as the artefact `result` with `if: always()` and `if-no-files-found: ignore`.
  If a step before the shim fails (checkout, set-up, token), there is no `result.json`; the run has failed, and its log says why.
- Inputs reach commands only through `env:`, never by `${{ }}` inside `run:` (AC4), so a crafted input cannot become shell.

### `ci` (`.github/workflows/ci.yml`)

On `pull_request` and on `push` to `main`. Never `pull_request_target`.

1. `check`: `make setup`, `make check`, `make test`. No secrets.
2. `fixture`: copies `tests/acceptance/fixture-site/` to a temporary folder, writes the commit under test (`github.event.pull_request.head.sha || github.sha`) to `commit.txt` in it, and uploads it as the artefact `fixture-site`. No secrets.
3. `acceptance`, after both: mints the App token for this repository, then runs `make acceptance` with `ACCEPTANCE_PROJECT=${{ github.repository }}`, `ACCEPTANCE_COMMIT` as above, `PLANE_ORG`, the Cloudflare secrets and `GITHUB_READ_TOKEN`.
   It has its own concurrency group, `acceptance`, never cancelled, because every run deploys the same fixture Worker.

So the plane deploys itself as its own fixture project: `agentic-orc-farm/cloudflare` with a component `site` becomes the public Worker `cloudflare-site-prod`, a few kilobytes that each CI run updates to its commit.
No real project can collide with it, because no other repository in the organisation is called `cloudflare`.
Pull requests from forks get no secrets, so their acceptance job fails; this repository takes changes only from its own branches.

What CI cannot test before merge is the `deploy` workflow itself, because `workflow_dispatch` runs only workflows that exist on the default branch.
CI runs the same command the workflow runs, and AC1 to AC4 check the workflow's wiring; the first dispatch after merge, a `plan` and an `apply` of the fixture by hand or by the driver in M5, is the live check of the workflow itself, and is not claimed before it has run.

## The `make` targets

| Target | Behind it |
|---|---|
| `make setup` | `uv sync --locked` and `npm ci` (installs the pinned wrangler into `node_modules/`). |
| `make check` | `ruff check`, `ruff format --check`, `pyright`, `lint-imports`, `zizmor .github/workflows`, `pip-audit` over the locked runtime dependencies, and `npm audit --omit=dev --audit-level=high`. |
| `make test` | `pytest -n auto tests/unit`: the shim with Cloudflare and GitHub faked through `httpx.MockTransport` and wrangler replaced by a scripted fake executable, no credentials, no network. |
| `make acceptance` | `pytest tests/acceptance`. The offline criteria need no credentials; the live ones need the variables above and fail, not skip, naming the missing ones, so a missing secret can never pass. `BASE_URL` does not apply: the plane has no address of its own. |
| `make package` | Prints that the plane is not packaged and exits 0. The plane is never deployed (the orchestrator's ADR 0012), so it has no artefact; the target exists because every project has the same six. |
| `make smoke ENV=<env>` | Prints that the plane has no environments and exits 0, for the same reason. |

## The stack

| Concern | Choice | Standard |
|---|---|---|
| Shim language | Python 3.13, uv, hatchling, `src/` layout, CLI archetype with the agent-facing section | Follows `PYTHON-BASE.md` and `PYTHON-CLI.md`. Not `PYTHON-WORKFLOW.md`: there is no journal or approval, by the request's "keeps no state of its own"; the driver holds the approvals. |
| Runtime dependencies | `pydantic` (frozen models at the boundary, as `PYTHON-BASE.md` section 5 asks) and `httpx`. | Follows, with a reason for `httpx`: one client for two APIs with per-request timeouts, the Authorization header dropped on cross-origin redirects (the artefact download), and `MockTransport` for credential-free tests. The standard library could do it with more code and more ways to leak a header. |
| Development dependencies | The template's set (pytest, pytest-cov, pytest-xdist, ruff, pyright, pip-audit, import-linter), plus `pyyaml` to read the workflows in tests and `zizmor` to lint them. | Follows; the two additions have their reasons in the row below and in AC1 to AC4. |
| Workflow linting | `zizmor`, which finds template injection, over-broad permissions and unpinned actions. | No standard covers it. This repository holds the organisation's deploy token, so its workflows are the riskiest code in it. |
| Platform tool | wrangler at an exact version (4.152.0 when checked on 2026-10-23), in a `package.json` and `package-lock.json` that hold nothing else, installed with `npm ci`, on Node 24 LTS. | No standard covers Node. wrangler 4 needs Node 22 or later; 24 is the current LTS line. |
| Dependency audit | `pip-audit` (standard) and `npm audit --omit=dev --audit-level=high` | `npm audit` has no standard; it covers the one tool that runs with the deploy token. If it blocks unrelated changes too often, lower it to a report and say so in `AGENTS.md`. |
| Actions | Pinned to a full commit SHA with the version in a comment. | Departs from `GITHUB.md` section 7 ("pin to a version") by being stricter, because a moved tag in any action here could read the deploy token. zizmor's `unpinned-uses` check enforces it. |
| CI | GitHub Actions, `ci.yml` as above, the baseline from `templates/ci.yml` split into `make` targets. | Follows `GITHUB.md` section 7 and `PYTHON-BASE.md` section 9; secrets only in the job that needs them. |
| Hosting | None: the plane is never deployed, so there is no `deploy.yaml`. | Follows the design brief. |

## Owner set-up, once

The README carries these as steps; the engineering agent cannot do them.

1. A Cloudflare account with a `workers.dev` subdomain chosen (Workers & Pages, once).
2. An account API token with `Workers Scripts: Edit` on that account only, saved as the repository secret `CLOUDFLARE_API_TOKEN`; the account id as the secret `CLOUDFLARE_ACCOUNT_ID`.
   I believe `Workers Scripts: Edit` covers the subdomain, deployment and script-subdomain reads; if CI shows a 403, the README records the extra permission (for example `Account Settings: Read`).
3. A second GitHub App, `agentic-orc-plane-reader` or similar, owned by `agentic-orc-farm`, with only `Actions: Read` (and the `Metadata: Read` GitHub adds), no webhook, installed on all the organisation's repositories.
   Its Client ID as the repository variable `PLANE_READER_CLIENT_ID`, its private key as the secret `PLANE_READER_PRIVATE_KEY`.
   It is not the driver's App: that one can write to every repository, and its key stays on the owner's machine (the orchestrator's ADR 0008).
4. Increment 2 adds: a Zero Trust organisation, the service token and the organisation secrets `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET`, and the Access permissions on the token.

This repository is public while the organisation is on GitHub Free, so its Actions logs are public: the shim logs Worker names and addresses, never tokens, account ids or response bodies.

## The cleanup runbook

`docs/cleanup.md`, one section per kind. Increment 1's `## static-site`: how to find a project's Workers (`<repo>-*-<env>`), remove one with `wrangler delete --name <worker>` or the dashboard, and that nothing else is created. Increment 2 adds the Access application and, once no project uses it, the policy.
It also says the fixture Worker `cloudflare-site-prod` belongs to this repository's CI and is recreated by the next run.

## Decision records

- `docs/adr/0001-resource-names.md`: Workers are `<repo>-<component>-<env>` on `workers.dev`, refused rather than rewritten when they do not fit, and only for projects in the plane's own organisation.
- `docs/adr/0002-reading-project-artefacts.md`: a read-only organisation GitHub App, a per-run token for one repository, and artefacts found by name and commit.
- `docs/adr/0003-a-stateless-shim.md`: a Python shim over a pinned wrangler that compares desired with observed state, a deployment marker as the only record of what runs, and `result.json` version 1 as the contract with the driver.

## What I could not verify

- That the artefacts API lists an artefact while its run is still in progress. The `upload-artifact` v4+ README says artefacts are available in the API as soon as they are uploaded; this repository's CI depends on it, and AC17 fails at once if it is wrong. The fallback is a fixture repository with a scheduled CI that keeps a fresh artefact.
- The exact shape of the Workers deployments API's annotations (`workers/message`), which the marker relies on. If it is not exposed, use `--tag` and the versions API instead; the criteria do not change.
- The minimal API token permissions (step 2 above).
- How long a new `workers.dev` address takes to answer; AC17 allows 120 seconds.
- The current major versions of `actions/checkout`, `astral-sh/setup-uv`, `actions/setup-node`, `actions/upload-artifact` and `actions/create-github-app-token` (v3, with `client-id` and `repositories` inputs): the engineering agent pins the latest at set-up.
