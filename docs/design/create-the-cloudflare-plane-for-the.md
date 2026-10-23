---
title: The Cloudflare plane for agentic-orc-farm
size: large
acceptance_tests: tests/acceptance/
criteria:
  # One pull request, all three environments. Ids are kept from earlier rounds; AC7, AC12, AC13 and AC14 were reworded in round 3, and criteria added in round 3 take AC31 onwards.
  # Offline: no credentials, no network. PLANE_ORG=agentic-orc-farm in the environment. Every refusal below happens during validation, before any credential is read.
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
  - id: AC32
    kind: new
    text: "The repository has `.github/workflows/acceptance.yml`, named `acceptance`, started only by `workflow_dispatch`, with exactly one input, `commit`, which is required; its `run-name` contains `inputs.commit`, and it checks out the repository at that commit."
  - id: AC33
    kind: new
    text: "No file under `.github/workflows/` that is started by `pull_request`, `pull_request_target` or `push` contains the text `secrets.`, and no workflow is started by `pull_request_target`; the only workflows that contain `secrets.` are `deploy.yml` and `acceptance.yml`, and each is started only by `workflow_dispatch`."
  - id: AC5
    kind: new
    text: "With no credentials in the environment, `uv run cf-plane wrangler-config --project agentic-orc-farm/example --env prod --component '{\"name\":\"site\",\"kind\":\"static-site\",\"plane\":\"cloudflare\",\"artefact\":\"site\"}' --assets DIR` exits 0 and prints JSON whose `name` is `example-site-prod`, `workers_dev` is true, `preview_urls` is false, `assets.directory` is DIR and `assets.not_found_handling` is `404-page`, with no `main` key."
  - id: AC31
    kind: new
    text: "The same command with `--env staging` exits 0 and prints JSON whose `name` is `example-site-staging`, `workers_dev` is true, `preview_urls` is false, `assets.directory` is DIR and `assets.not_found_handling` is `404-page`, with no `main` key."
  - id: AC6
    kind: new
    text: "With no credentials in the environment, `uv run cf-plane deploy` given a component whose kind is not `static-site` exits non-zero and writes a `result.json` whose `components` is empty and whose `summary` names the unknown kind and names `static-site` as the kind offered."
  - id: AC7
    kind: new
    text: "With no credentials in the environment and ACCESS_OWNER_EMAIL unset, `uv run cf-plane deploy` with otherwise valid inputs and `--env dev`, or `--env staging`, exits non-zero and writes a `result.json` whose `components` is empty and whose `summary` names `ACCESS_OWNER_EMAIL`; the same command with `--env prod` also exits non-zero (it has no credentials), and its `summary` does not contain `ACCESS_OWNER_EMAIL`."
  - id: AC8
    kind: new
    text: "With no credentials in the environment, `uv run cf-plane deploy` with a `--commit` that is not 40 lowercase hexadecimal characters exits non-zero and writes a `result.json` whose `components` is empty and whose `summary` names `commit`."
  - id: AC23
    kind: new
    text: "With no credentials in the environment, `uv run cf-plane deploy` with a `--project` whose owner is not the organisation named in `PLANE_ORG` exits non-zero and writes a `result.json` whose `components` is empty and whose `summary` names `project` and `agentic-orc-farm`."
  - id: AC24
    kind: new
    text: "With no credentials in the environment, `uv run cf-plane deploy` with a `--project` whose repository name contains a character other than a lowercase letter, a digit or a dash (for example `agentic-orc-farm/My.Site`) exits non-zero and writes a `result.json` whose `components` is empty and whose `summary` names `project`."
  - id: AC25
    kind: new
    text: "With no credentials in the environment, `uv run cf-plane deploy` given a component whose `plane` is not `cloudflare` exits non-zero and writes a `result.json` whose `components` is empty and whose `summary` names that component and `plane`."
  - id: AC26
    kind: new
    text: "With no credentials in the environment, `uv run cf-plane deploy` given two components with the same name exits non-zero and writes a `result.json` whose `components` is empty and whose `summary` names the repeated name."
  - id: AC27
    kind: new
    text: "With no credentials in the environment, `uv run cf-plane deploy` with `--components` that is not valid JSON, is an empty list, or has an item without exactly the keys name, kind, plane and artefact, exits non-zero in each case and writes a `result.json` whose `components` is empty and whose `summary` names `components`."
  - id: AC9
    kind: new
    text: "With no credentials in the environment, `uv run cf-plane deploy` for a component whose Worker name (`<repo>-<component>-<env>`) would be longer than 63 characters exits non-zero and writes a `result.json` whose `summary` contains that Worker name and the number 63."
  - id: AC10
    kind: new
    text: "Every `result.json` written by the refusals of AC6 to AC9 and AC23 to AC27 is a JSON object with exactly the keys `schema_version` (the integer 1), `components` (an empty list) and `summary` (a string of at most 1000 characters)."
  - id: AC11
    kind: new
    text: "`package.json` pins `wrangler` to an exact version (digits and dots only, no range), and `package-lock.json` records the same version for `node_modules/wrangler`."
  - id: AC12
    kind: new
    text: "`make test` and `make acceptance` each exit 0 with ACCEPTANCE_LIVE, CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, GITHUB_READ_TOKEN, CF_ACCESS_CLIENT_ID, CF_ACCESS_CLIENT_SECRET and ACCESS_OWNER_EMAIL removed from their environment, once the build is done."
  - id: AC13
    kind: new
    text: "README.md has a `## Kinds` section that lists `static-site`, and names the repository secrets CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, PLANE_READER_PRIVATE_KEY and ACCESS_OWNER_EMAIL, the repository variable PLANE_READER_CLIENT_ID, the Access service token name `orc-plane-tests`, and the workflow `acceptance` as the place the live acceptance criteria run."
  - id: AC34
    kind: new
    text: "README.md has a `## Private environments` section that names the organisation secrets CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET and the request headers `CF-Access-Client-Id` and `CF-Access-Client-Secret`, and says that `prod` is public and `dev` and `staging` are not."
  - id: AC14
    kind: new
    text: "`docs/cleanup.md` has a `## static-site` section, and under it a `### Access` section."
  # Live: only in this repository's `acceptance` workflow, dispatched with a `commit`, which sets ACCEPTANCE_LIVE=1, ACCEPTANCE_PROJECT (this repository) and ACCEPTANCE_COMMIT (the input), and passes the secrets.
  # <owner> and <repo> are ACCEPTANCE_PROJECT's owner and repository name; <subdomain> is the account's workers.dev subdomain.
  # The fixture site is the test agent's to provide, in tests/acceptance/fixture-site/: an `index.html`, and a `404.html` whose body contains text found in no other file of the fixture.
  # It has no `commit.txt`: the `fixture` job of `ci.yml`, which runs without secrets on every push, writes that file and uploads the folder as the artefact `fixture-site` for the commit.
  # "The headers" means `CF-Access-Client-Id: $CF_ACCESS_CLIENT_ID` and `CF-Access-Client-Secret: $CF_ACCESS_CLIENT_SECRET`. Requests do not follow redirects.
  # With ACCEPTANCE_LIVE unset, each live test is skipped with a reason naming the `acceptance` workflow. With ACCEPTANCE_LIVE=1 and a variable these criteria need missing, each live test fails and names the missing variables.
  - id: AC15
    kind: new
    text: "A plan to prod for a component named `plan-only` (kind static-site, artefact fixture-site) exits 0, lists `plan-only` with the url `https://<repo>-plan-only-prod.<subdomain>.workers.dev`, has the line `plan-only: would create Worker <repo>-plan-only-prod` in its summary, and afterwards the account has no Worker named `<repo>-plan-only-prod`."
  - id: AC16
    kind: new
    text: "A plan to prod for a component `site` with GITHUB_READ_TOKEN unset, for a commit with no artefacts (forty zeros), exits 0 and lists `site` with the url `https://<repo>-site-prod.<subdomain>.workers.dev`."
  - id: AC17
    kind: new
    text: "An apply to prod of a component `fixture-web` with artefact `fixture-site` for the fixture commit exits 0 and lists `fixture-web` with the url `https://<repo>-fixture-web-prod.<subdomain>.workers.dev`, and within 120 seconds a GET of `<url>/commit.txt`, without the headers, returns 200 with the fixture commit as its body."
  - id: AC18
    kind: new
    text: "After that apply, a GET of `<url>/no-such-page` returns 404 with the body of the fixture's `404.html`."
  - id: AC19
    kind: new
    text: "After that apply, Cloudflare's script subdomain API reports `enabled` true and `previews_enabled` false for the Worker `<repo>-fixture-web-prod`."
  - id: AC43
    kind: new
    text: "After that apply, the account has no Access application with a destination for the Worker `<repo>-fixture-web-prod`."
  - id: AC20
    kind: new
    text: "A second apply with the same inputs exits 0, lists the same url, has the line `fixture-web: unchanged` in its summary, and leaves the Worker's active deployment id as it was after the first apply."
  - id: AC21
    kind: new
    text: "A plan with the same inputs after the apply exits 0, has the line `fixture-web: unchanged` in its summary, and leaves the Worker's active deployment id as it was."
  - id: AC22
    kind: new
    text: "An apply of `fixture-web` for a commit with no `fixture-site` artefact (forty zeros) exits non-zero, its summary contains `fixture-site` and that commit, and the Worker's active deployment id does not change."
  - id: AC29
    kind: new
    text: "After the apply of AC17, an apply to prod for the project `<owner>/<repo>-fixture` with a component `web` (kind static-site, artefact fixture-site), whose Worker name is also `<repo>-fixture-web-prod`, exits non-zero, writes a `result.json` whose `components` is empty and whose `summary` has the line `web: Worker <repo>-fixture-web-prod belongs to <ACCEPTANCE_PROJECT>` (the whole line, so the asking project's longer name does not satisfy it), and the Worker's active deployment id does not change."
  - id: AC30
    kind: new
    text: "After the apply of AC17, a plan to prod for the project `<owner>/<repo>-fixture` with a component `web` (kind static-site, artefact fixture-site) exits non-zero and writes a `result.json` whose `components` is empty and whose `summary` has the line `web: Worker <repo>-fixture-web-prod belongs to <ACCEPTANCE_PROJECT>`."
  # Private environments. Before AC35, the test removes any Access application with a destination for the Worker `<repo>-fixture-web-dev` or `<repo>-fixture-web-staging`, then those Workers, so every run starts from nothing. It never removes the shared policies or the service token.
  - id: AC35
    kind: new
    text: "With no Worker named `<repo>-fixture-web-dev`, a plan to dev of `fixture-web` (artefact fixture-site) for the fixture commit exits 0, lists `fixture-web` with the url `https://<repo>-fixture-web-dev.<subdomain>.workers.dev`, has the line `fixture-web: would create Worker <repo>-fixture-web-dev, would create Access application <repo>-fixture-web-dev` in its summary, and afterwards the account has no Worker named `<repo>-fixture-web-dev` and no Access application with a destination for it."
  - id: AC36
    kind: new
    text: "Then an apply to dev with the same inputs exits 0, lists the same url, and within 120 seconds a GET of `<url>/commit.txt` with the headers returns 200 with the fixture commit as its body."
  - id: AC37
    kind: new
    text: "A GET of `<url>/commit.txt` without the headers, repeated once a second from just before the apply of AC36 starts until 30 seconds after it exits, never returns 200."
  - id: AC38
    kind: new
    text: "After that apply, a GET of `<url>/commit.txt` without the headers does not return 200 and its body does not contain the fixture commit."
  - id: AC39
    kind: new
    text: "After that apply, the account has exactly one Access application with a destination for the Worker `<repo>-fixture-web-dev`; its policies are exactly the reusable policy `orc-plane-service-token`, whose decision is `non_identity` and which includes the service token named `orc-plane-tests`, and the reusable policy `orc-plane-owner`, whose decision is `allow` and which includes the email in ACCESS_OWNER_EMAIL; and its allowed identity providers are exactly the account's one-time PIN provider."
  - id: AC40
    kind: new
    text: "A second apply to dev with the same inputs exits 0, has the line `fixture-web: unchanged` in its summary, leaves the Worker's active deployment id as it was after the first apply, and afterwards the account has exactly one Access application with a destination for the Worker, exactly one reusable Access policy named `orc-plane-service-token` and exactly one named `orc-plane-owner`."
  - id: AC41
    kind: new
    text: "After the applies to dev, Cloudflare's script subdomain API reports `enabled` true and `previews_enabled` false for the Worker `<repo>-fixture-web-dev`."
  - id: AC42
    kind: new
    text: "A plan to staging of `fixture-web` (artefact fixture-site) for the fixture commit exits 0, lists the url `https://<repo>-fixture-web-staging.<subdomain>.workers.dev`, has the line `fixture-web: would create Worker <repo>-fixture-web-staging, would create Access application <repo>-fixture-web-staging` in its summary, and afterwards the account has no Worker named `<repo>-fixture-web-staging`."
  - id: AC28
    kind: new
    text: "Every `result.json` written by the plans and applies of AC15 to AC22, AC29, AC30 and AC35 to AC42 is a JSON object with exactly the keys `schema_version` (the integer 1), `components` (a list of objects with exactly the keys `name` and `url`) and `summary` (a string of at most 1000 characters)."
---


# The Cloudflare plane for agentic-orc-farm

The request fixes the contract: one `deploy` workflow (`workflow_dispatch`, inputs `project`, `commit`, `env`, `mode`, `components`), one kind (`static-site`: a Worker with static assets, Access in front of dev and staging, prod public), a stateless shim that writes a wrangler configuration and runs a pinned wrangler, `result.json` uploaded as a run artefact, safe repeat applies, a README and a cleanup runbook.
The options below differ only in what the request leaves open: the shim's language, how Access is set up, and how the workflow reads another repository's artefacts.

## Facts every option rests on

Checked on 2026-10-23.

- **wrangler** is 4.152.0 and needs Node 22 or later, so every option has Node on the runner.
- **wrangler does not manage Access.** The one-click "Enable Cloudflare Access" for `workers.dev` (changelog, 2025-10-03) is dashboard-only, with no API or wrangler option named.
  (Corrected in the design pass: Cloudflare's Workers documentation now also describes Access applications with a `worker` destination, created through the API; the design uses it, and ADR 0004 records why.)
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
(The owner overruled the split in design review: one pull request covers all three environments. See the design below.)

## Questions for the design pass

- **Hostnames.** `workers.dev` (`<worker>.<account-subdomain>.workers.dev`) needs no zone and is what I would use. A custom domain needs a zone the request does not name. I assume `workers.dev`.
- **Who else passes Access.** The request names only the service token. The owner will probably want to open dev and staging in a browser, which needs an email rule and a login method (one-time PIN is the lightest). I would ask before adding it.
- **Worker names.** Workers names are limited to 63 characters, lowercase letters, digits and dashes. I would use `<repo>-<env>` and refuse names that do not fit, rather than truncate and risk two projects sharing a Worker.


# Design

Chosen: Option A, a Python shim, with an organisation-owned, read-only GitHub App for reading project artefacts.
The reason given: Python follows the owner's checked standards and CI baseline and keeps the find-or-create logic in pure, locally tested functions; the App gives short-lived, read-only tokens scoped to one repository that belong to the organisation rather than a person.

Round 3 follows the owner's review:

- **One pull request for all three environments.** Projects deploy to dev first and prod last, so a plane without private environments serves no project. Access for dev and staging is in this pull request, with the owner let through by email and a one-time PIN.
- **Live tests follow "Deploy once".** CI checks every push without secrets. The live criteria run only in a separate `acceptance` workflow, started by `workflow_dispatch` for one reviewed commit. No `pull_request` or `push` job sees a secret.

The questions the options pass left open are settled like this:

- **Hostnames:** `workers.dev` only (`https://<worker>.<account subdomain>.workers.dev`). No zone or custom domain: a domain for prod waits for a request that names one (the orchestrator's ADR 0012 lists it as owner set-up "if prod needs one").
- **Who passes Access:** the organisation's read-only service token, for projects' tests; and the owner's email, with a one-time PIN, for a browser. Nobody else.
- **Worker names:** `<repo>-<component>-<env>`, refused rather than truncated when they do not fit (ADR 0001). The request says "named after the project and environment"; the component name is added because `deploy.yaml` may list several static sites, and without it two components of one project would deploy over each other.
  Because repository and component names may both contain dashes, two projects can still map to one Worker name (`shop` with `admin-site`, and `shop-admin` with `site`, are both `shop-admin-site-prod`). The deployment marker names the project that owns the Worker, and the plane refuses to plan or apply onto a Worker owned by another project (below, and ADR 0001). The first project to deploy keeps the name; the second is told to rename its component.

There are no increments: this is one pull request.

## The smallest version

One command, `cf-plane deploy`, run by one workflow, does this:

1. **Validate** every input before reading any credential (`cf-plane validate` runs the same checks on its own, so the workflow can stop early and still write `result.json`).
2. **Translate** each component into its desired state: Worker name, wrangler configuration, address, deployment marker, and, for dev and staging, its Access application. Pure.
3. **Observe** with read-only calls: each Worker (does it exist, its recent deployments and their markers, its workers.dev and preview settings) and, for dev and staging, the Access objects below.
4. **Compare** desired with observed into one change per component, made of parts (create, update or unchanged for the Worker, and for its Access application), or a refusal (below). Pure.
   Every component and every shared Access object is observed and compared before anything changes, so a refusal at this stage changes nothing.
5. In `plan` mode, stop: report the changes and the addresses.
   In `apply` mode, make the changes in the order below.
6. **Write `result.json`** and exit 0, or exit 1 with the reason on stderr and in the summary.

It keeps nothing between runs: Cloudflare is the record of what exists, and the marker on the active deployment is the record of what is running.

### The deployment marker

`wrangler deploy --message "orc project=<owner/repo> commit=<commit> config=<hash>"`, where `<hash>` is the first 12 hex digits of the SHA-256 of the canonical JSON of the wrangler configuration without the assets folder's path, `workers_dev` and `preview_urls`.
Those two are left out because the shim reads them directly from the script subdomain API, and because a new private Worker is first deployed with `workers_dev` off (below).
wrangler stores the message as the deployment's `annotations["workers/message"]`, which the deployments API returns (checked in Cloudflare's API reference on 2026-10-23).

- **Owner.** A Worker's owner is the project named in the newest deployment, among those the deployments API lists, whose message is a plane marker. The owner is read from the history rather than only the active deployment, so a rollback made by hand on the dashboard (a deployment with no marker) does not orphan the Worker.
- **Refusals.** If the Worker exists and its owner is another project, the plan or apply is refused, naming the Worker, the owning project and the project asking, and saying that a different component name gives a different Worker. If the Worker exists and no listed deployment carries a plane marker, it was not made by the plane (or is older than the history the API lists), and the plan or apply is refused, naming the Worker and pointing to the runbook.
- **Worker unchanged** when it exists, is owned by the project asking, its active deployment carries exactly the desired marker, workers.dev is on and previews are off. Otherwise its part is `update` (owned, but different) or `create` (absent).

So a second apply runs no wrangler, a plan after an apply says `unchanged`, a change to the plane's translation redeploys exactly the components it affects, and one project can never overwrite another's Worker.
Two limits: a change made by hand on the dashboard that does not create a deployment (for example a variable) is not seen; and two colliding projects whose first applies race each other could both see no Worker and both deploy, because the concurrency group is per project, not per Worker. The second needs two projects created with colliding names and first deployed in the same minute; the runbook says how to spot and fix it.

### Access in front of dev and staging

`prod` has no Access objects: its Workers are public. For `dev` and `staging`, ADR 0004 records the choices.

| Object | Who makes it | Found by | Desired |
|---|---|---|---|
| Zero Trust organisation | the owner, once | (the account has one) | |
| One-time PIN login method | the owner, once | `GET /access/identity_providers`, the one of type `onetimepin` | |
| Service token `orc-plane-tests` | the owner, once | `GET /access/service_tokens`, by exact name | |
| Policy `orc-plane-service-token` | the shim, shared by every private Worker | `GET /access/policies` (reusable), by exact name | decision `non_identity`, include exactly the service token's id |
| Policy `orc-plane-owner` | the shim, shared by every private Worker | the same, by exact name | decision `allow`, include exactly the email in `ACCESS_OWNER_EMAIL` |
| Application `<worker>`, one per private Worker | the shim | `GET /access/apps`, the ones with a destination `{"type": "worker", "worker_id": <the Worker's id>}` | `type` `self_hosted`, name `<worker>`, destinations exactly that Worker, policies exactly the two above (precedence 1 and 2), `allowed_idps` exactly the one-time PIN provider, `auto_redirect_to_identity` true, `app_launcher_visible` false |

- A `worker` destination protects every address of the Worker, including workers.dev, previews and any later route, not only one hostname (Cloudflare's Workers documentation, "Cloudflare Access", read on 2026-10-23).
- **Refusals**, all before anything changes: `ACCESS_OWNER_EMAIL` unset or not an email (during validation, before any credential is read; AC7); no one-time PIN provider, or no service token named `orc-plane-tests`, or more than one (naming the README step that makes it); two policies with one of the plane's names, or two applications for one Worker (naming them and the runbook).
- A shared policy that differs (for example the service token was rotated, so its id changed, or the owner's email changed) is updated in place, which fixes every private Worker at once.
- An application that differs is updated in place. An application that is missing for an existing Worker (deleted by hand) is created.
- The Worker's ownership is checked first, so the shim never touches the application of a Worker another project owns.

**Order of an apply to dev or staging**, so a Worker is never reachable before its application exists:

1. Create or update the two shared policies.
2. For each component whose Worker does not exist: download its artefact and run wrangler with `workers_dev: false` and `preview_urls: false`. The Worker now exists, with the desired marker, at no address.
3. Read the Worker's id; create or update its Access application.
4. For each component whose Worker now carries the desired marker but has workers.dev off or previews on (a Worker made in step 2, or one left so by an apply that failed part way): turn workers.dev on with previews off through the script subdomain API (`POST /accounts/{account}/workers/scripts/{name}/subdomain`, `enabled: true`, `previews_enabled: false`).
5. For each component whose Worker existed with a different marker: download its artefact and run wrangler with the desired configuration (`workers_dev: true`, `preview_urls: false`).

One rule spans steps 4 and 5: after creating an application in step 3, wait 30 seconds, once per apply, before any step that makes a Worker reachable, so Access has taken effect.
An existing Worker whose application was deleted by hand is already reachable; step 3 closes it before anything else happens to it, and the plan shows `would create Access application`.

AC37 checks the order from outside: a request without the headers, once a second through the whole apply that creates the dev Worker, never gets a 200.
How long Access takes to apply a new application at the edge I could not verify; 30 seconds is a guess that AC37 tests, and the engineering agent raises it if AC37 fails.

### Inputs and refusals

| Input | Rule |
|---|---|
| `project` | `<org>/<repo>`, where `<org>` equals `PLANE_ORG` (the workflow sets it from `github.repository_owner`) and `<repo>` matches `[a-z0-9-]+`. Other characters are refused, not rewritten: rewriting `my.site` and `my-site` to one name would make two projects ask for one Worker. Names that still meet through dashes are caught by the owner check on the marker. |
| `commit` | 40 lowercase hexadecimal characters. |
| `env` | `dev`, `staging` or `prod`. For `dev` and `staging`, `ACCESS_OWNER_EMAIL` must be set and look like an email (one `@`, no spaces). |
| `mode` | `plan` or `apply`. |
| `components` | A non-empty JSON list; each item has exactly `name`, `kind`, `plane` and `artefact`, each matching `[a-z0-9][a-z0-9-]{0,62}` (as the driver's `deploy.yaml` check does); `plane` is `cloudflare`; `kind` is one the plane offers (`static-site`); names are unique; each Worker name is at most 63 characters. |

A refusal names the input, says what is wrong and what would satisfy it, and is safe to paste into a prompt (`PYTHON-CLI.md` section 2).
Validation reads no environment variable except `PLANE_ORG` and `ACCESS_OWNER_EMAIL`, so every refusal above happens with no credentials present. The email is never written to `result.json` or the log.

### `result.json`, schema version 1

```json
{
  "schema_version": 1,
  "components": [{"name": "site", "url": "https://example-site-dev.acme.workers.dev"}],
  "summary": "dev plan for agentic-orc-farm/example at <commit>\nAccess policy orc-plane-service-token: unchanged\nAccess policy orc-plane-owner: unchanged\nsite: would create Worker example-site-dev, would create Access application example-site-dev"
}
```

- Exactly these three keys; `components` items have exactly `name` and `url`; `summary` is at most 1000 characters.
  A summary that would be longer keeps its first line and as many whole lines as fit, then ends with the line `(N more lines: see the run log)`; the full summary is always in the Actions log.
- `url` is computed (`https://<worker>.<subdomain>.workers.dev`), not parsed from wrangler's output, so a plan gives the address an apply will produce.
- The summary's first line says the env, mode, project and commit.
  For dev and staging, one line for each shared policy follows: `Access policy <name>: ` and `would create`, `would update`, `unchanged`, `created` or `updated`.
  Then one line per component: `<name>: unchanged`, or the parts that change, joined by `, `, in this order: `would create Worker <worker>` or `would update Worker <worker>`, then `would create Access application <worker>` or `would update Access application <worker>`. An apply says `created` and `updated` instead of `would create` and `would update`.
- On a refusal, `components` is empty and the summary is the refusal. An owner-check refusal has one line per refused component, exactly `<name>: Worker <worker> belongs to <owner/repo>` or `<name>: Worker <worker> was not deployed by the plane`, followed by what to do (rename the component, or see the runbook).
- On a failure part way through an apply, `components` lists the components that are live at the new marker, the summary says which component failed and why, and the run fails. Running the same apply again finishes the job; a private Worker left at step 2 is at no address until it does.
- The run's conclusion (success or failure) is the driver's signal; `result.json` is the detail.

### Reading the artefact

Only `apply` reads artefacts, so a plan works for a commit whose CI has not packaged anything yet, which is the case at the design gate.

- The workflow mints an installation token from the plane's GitHub App (ADR 0002) with `actions/create-github-app-token`, scoped to the one project repository and to `permission-actions: read`, and passes it to the shim as `GITHUB_READ_TOKEN`.
- The shim lists the project's artefacts with that component's `artefact` name (`GET /repos/{project}/actions/artifacts?name=<artefact>`, paginated), keeps those whose `workflow_run.head_sha` is the commit, whose `workflow_run.head_repository_id` equals `workflow_run.repository_id` (so no run started from a fork) and that have not expired, and takes the newest.
  It does not require the CI run to have passed: the driver asks for a deploy only after CI is green. ADR 0002 records this.
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

- The same for every environment; the only difference is the name. The first deploy of a new private Worker overrides `workers_dev` to false (step 2 above), and the marker's hash leaves `workers_dev` out, so the next apply sees no difference.
- Assets only, no `main`: the artefact is served as it is, with no code of the plane's.
- `preview_urls` is set explicitly so a later default in wrangler cannot reopen previews.
- `not_found_handling: "404-page"` serves the nearest `404.html` with status 404, which is what the owner's static-site baseline asks for (`UI.md`, a real 404); an artefact without one gets Cloudflare's plain 404.
- `cf-plane wrangler-config` prints this for a component, with no credentials and no network (AC5, AC31); it is the local, credential-free view of the translation the request asks for.

### Commands

Declared as data in `cli.py`, as `PYTHON-CLI.md` section 4 asks:

| Command | Does | Needs |
|---|---|---|
| `cf-plane validate --project --commit --env --mode --components --result PATH` | Checks the inputs; prints the repository name on success; writes `result.json` and exits 1 on a refusal. | `PLANE_ORG`; `ACCESS_OWNER_EMAIL` for dev and staging |
| `cf-plane deploy` (same arguments) | Everything above. | As `validate`, and `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`; `GITHUB_READ_TOKEN` for `apply` only |
| `cf-plane wrangler-config --project --env --component JSON --assets DIR` | Prints one component's wrangler configuration. | Nothing |

### Layout and layering

```
src/cf_plane/
  contract.py      inputs, components and result.json as frozen pydantic models                pure
  static_site.py   the kind: Worker name, address, wrangler configuration, marker, Access app   pure
  access.py        the desired shared policies; finding and comparing Access objects           pure
  changes.py       desired against observed, into parts and refusals; the apply order; the summary   pure
  cloudflare.py    the Cloudflare API: subdomain, Worker, deployments, script subdomain, Access
  artefacts.py     find, download and safely unpack a project's artefact
  wrangler.py      write wrangler.json, run node_modules/.bin/wrangler
  cli.py           the commands, and writing result.json
```

- An import-linter contract: `cli` above `cloudflare | artefacts | wrangler` above `changes` above `static_site | access` above `contract`; and `contract`, `static_site`, `access` and `changes` may not import `httpx` or `subprocess`.
- The apply order is data that `changes.py` returns (a list of steps), so unit tests check it without a fake clock or network.
- Kinds are a dict in `changes.py` (`{"static-site": static_site}`); there is no plugin mechanism until a second kind exists.
- Every call has a timeout: 30 seconds per HTTP request, 120 seconds for an artefact download, 300 seconds for wrangler, run in its own process group and killed as a group (`PYTHON-BASE.md` section 6).
- No automatic retries: an apply is safe to run again, so the retry is running the workflow again.
- wrangler runs with `WRANGLER_SEND_METRICS=false`, and with `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` from the environment; the shim never logs either, nor `GITHUB_READ_TOKEN`, `ACCESS_OWNER_EMAIL` or any Access response body.
- Before each outside effect the shim logs what it is about to do, and after it what happened (`PYTHON-CLI.md` section 3), to the Actions log; there is no journal because the plane keeps no state.

## The workflows

Only two workflows hold secrets, and both are started only by `workflow_dispatch`, which needs write access to this repository (AC33).

### `deploy` (`.github/workflows/deploy.yml`)

- `on: workflow_dispatch` with the five required string or choice inputs and nothing else; `run-name` shows mode, project, env and commit, so the driver and the owner can find a run.
- `permissions: contents: read`. The secrets reach only the steps that call the shim.
- `concurrency: group: deploy-${{ inputs.project }}-${{ inputs.env }}`, `cancel-in-progress: false`, so two applies for one project and env never overlap.
  GitHub keeps only one pending run per group and cancels an older pending one when a third arrives; the driver must treat a cancelled run as "ask again". (From GitHub's documented behaviour; not tested here.)
- `timeout-minutes: 15`.
- Steps: checkout; set up uv and Node; `make setup`; `cf-plane validate` (its output is the repository name); for `apply` only, mint the App token for that repository; `cf-plane deploy`; upload `result.json` as the artefact `result` with `if: always()` and `if-no-files-found: ignore`.
  If a step before the shim fails (checkout, set-up, token), there is no `result.json`; the run has failed, and its log says why.
- Inputs reach commands only through `env:`, never by `${{ }}` inside `run:` (AC4), so a crafted input cannot become shell.

### `ci` (`.github/workflows/ci.yml`)

On `pull_request` and on `push` to `main`. Never `pull_request_target`. No secrets in any job (AC33).

1. `check`: `make setup`, `make check`, `make test`, `make acceptance` (the offline criteria; the live ones are skipped because `ACCEPTANCE_LIVE` is not set).
2. `fixture`: copies `tests/acceptance/fixture-site/` to a temporary folder, writes the commit under test (`github.event.pull_request.head.sha || github.sha`) to `commit.txt` in it, and uploads it as the artefact `fixture-site`.
   This is the plane's own fixture project's CI, in the same shape as any project's: it packages on every push, and the plane deploys a commit only when asked.
   The fixture folder belongs to the test agent, because it sits inside `tests/acceptance/`: it holds an `index.html` and a `404.html` whose body has text found in no other fixture file, and no `commit.txt`, because this job writes it. Engineering's `ci.yml` only refers to the folder and never writes into it.

### `acceptance` (`.github/workflows/acceptance.yml`)

The live criteria, for one commit, when the driver asks (the flow's "Deploy once": only for a commit that passed review).

- `on: workflow_dispatch` with one required input, `commit`; `run-name: acceptance ${{ inputs.commit }}`, so the driver finds its run by name (the run's own `head_sha` is the dispatching branch's, not the input).
- The driver dispatches it on `main`, so the workflow definition that receives the secrets is always a merged one; it checks out `commit` and runs that commit's tests.
- `permissions: contents: read`; `concurrency: group: acceptance`, `cancel-in-progress: false`; `timeout-minutes: 30`.
- Steps: check that `commit` is 40 lowercase hexadecimal characters (through `env:`); checkout at `commit`; set up uv and Node; `make setup`; mint the App token for this repository; `make acceptance` with `ACCEPTANCE_LIVE=1`, `ACCEPTANCE_PROJECT=${{ github.repository }}`, `ACCEPTANCE_COMMIT` (the input), `PLANE_ORG`, the Cloudflare secrets, `ACCESS_OWNER_EMAIL`, `CF_ACCESS_CLIENT_ID`, `CF_ACCESS_CLIENT_SECRET` and `GITHUB_READ_TOKEN`.
- It reads the `fixture-site` artefact that `ci.yml` uploaded for the commit, so the driver dispatches it only once CI is green for that commit (as it does for any project's deploy). If CI has not run, AC17 fails, naming the artefact and the commit.
- The plane deploys itself as its own fixture project: `agentic-orc-farm/cloudflare` with a component `fixture-web` becomes `cloudflare-fixture-web-prod` (public) and `cloudflare-fixture-web-dev` (behind Access), a few kilobytes each. AC29 and AC30 ask, as the project `agentic-orc-farm/cloudflare-fixture` with a component `web`, for the prod name, and check the owner check refuses; no repository of that name needs to exist, because the refusal comes before any artefact is read.
- Nothing else deploys the plane's own fixture. A hand-dispatched `deploy` of `agentic-orc-farm/cloudflare` is in a different concurrency group and could overlap an acceptance run; the README says not to.

**Bootstrap.** GitHub runs `workflow_dispatch` only for a workflow file that is on the default branch (GitHub's "Manually running a workflow", read on 2026-10-23), and this pull request is what adds `acceptance.yml`.
So, once, before the driver can run this pull request's live criteria, the owner copies `.github/workflows/acceptance.yml` from the reviewed commit to `main` (a one-file commit, or a pull request holding only that file).
After that, the merged definition is the one that runs, and changes to it arrive by merge like any other.
The same holds for `deploy.yml`: the first real dispatch of it is after merge, and is not claimed before it has run. The live criteria run the same command it runs, and AC1 to AC4 check its wiring.

## The `make` targets

| Target | Behind it |
|---|---|
| `make setup` | `uv sync --locked` and `npm ci` (installs the pinned wrangler into `node_modules/`). |
| `make check` | `ruff check`, `ruff format --check`, `pyright`, `lint-imports`, `zizmor .github/workflows`, `pip-audit` over the locked runtime dependencies, and `npm audit --omit=dev --audit-level=high`. |
| `make test` | `pytest -n auto tests/unit`: the shim with Cloudflare and GitHub faked through `httpx.MockTransport` and wrangler replaced by a scripted fake executable, no credentials, no network. |
| `make acceptance` | `pytest tests/acceptance`. The offline criteria (AC1 to AC14, AC23 to AC27, AC31 to AC34) need no credentials and always run. The live criteria (AC15 to AC22, AC28 to AC30, AC35 to AC43) run only when `ACCEPTANCE_LIVE=1`, which only the `acceptance` workflow sets; then each needs `ACCEPTANCE_PROJECT`, `ACCEPTANCE_COMMIT`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `GITHUB_READ_TOKEN`, `ACCESS_OWNER_EMAIL`, `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET`, and fails naming any that is missing, so a missing secret can never pass. Without `ACCEPTANCE_LIVE`, each live test is skipped with the reason "live: runs in the `acceptance` workflow, dispatched for a reviewed commit". So `ci.yml` and a local run show the offline criteria; the live ones are evidenced only by a successful `acceptance` run whose name carries the commit, and the engineering, test and review agents say so rather than claim them. The owner's machine never holds the deploy token. `BASE_URL` does not apply: the plane has no address of its own. |
| `make package` | Prints that the plane is not packaged and exits 0. The plane is never deployed (the orchestrator's ADR 0012), so it has no artefact; the target exists because every project has the same six. |
| `make smoke ENV=<env>` | Prints that the plane has no environments and exits 0, for the same reason. |

## The stack

| Concern | Choice | Standard |
|---|---|---|
| Shim language | Python 3.13, uv, hatchling, `src/` layout, CLI archetype with the agent-facing section | Follows `PYTHON-BASE.md` and `PYTHON-CLI.md`. Not `PYTHON-WORKFLOW.md`: there is no journal or approval, by the request's "keeps no state of its own"; the driver holds the approvals. |
| Runtime dependencies | `pydantic` (frozen models at the boundary, as `PYTHON-BASE.md` section 5 asks) and `httpx`. | Follows, with a reason for `httpx`: one client for two APIs with per-request timeouts, the Authorization header dropped on cross-origin redirects (the artefact download), and `MockTransport` for credential-free tests. The standard library could do it with more code and more ways to leak a header. |
| Development dependencies | The template's set (pytest, pytest-cov, pytest-xdist, ruff, pyright, pip-audit, import-linter), plus `pyyaml` to read the workflows in tests and `zizmor` to lint them. | Follows; the two additions have their reasons in the row below and in AC1 to AC4, AC32 and AC33. |
| Workflow linting | `zizmor`, which finds template injection, over-broad permissions and unpinned actions. | No standard covers it. This repository holds the organisation's deploy token, so its workflows are the riskiest code in it. |
| Platform tool | wrangler at an exact version (4.152.0 when checked on 2026-10-23), in a `package.json` and `package-lock.json` that hold nothing else, installed with `npm ci`, on Node 24 LTS. | No standard covers Node. wrangler 4 needs Node 22 or later; 24 is the current LTS line. |
| Access | The Cloudflare Access API, called by the shim; wrangler has no Access support. | No standard covers it; ADR 0004. |
| Dependency audit | `pip-audit` (standard) and `npm audit --omit=dev --audit-level=high` | `npm audit` has no standard; it covers the one tool that runs with the deploy token. If it blocks unrelated changes too often, lower it to a report and say so in `AGENTS.md`. |
| Actions | Pinned to a full commit SHA with the version in a comment. | Departs from `GITHUB.md` section 7 ("pin to a version") by being stricter, because a moved tag in any action here could read the deploy token. zizmor's `unpinned-uses` check enforces it. |
| CI | GitHub Actions: `ci.yml` without secrets on every push, the baseline from `templates/ci.yml` split into `make` targets; live tests in `acceptance.yml`, dispatched. | Follows `GITHUB.md` section 7 ("only the job that needs one gets it") and `PYTHON-BASE.md` section 9, and the orchestrator's flow ("Deploy once"). |
| Hosting | None: the plane is never deployed, so there is no `deploy.yaml`. | Follows the design brief. |

## Owner set-up, once

The README carries these as numbered steps; the engineering agent cannot do them.

1. A Cloudflare account with a `workers.dev` subdomain chosen (Workers & Pages, once).
2. A Zero Trust organisation on that account (the free plan covers up to 50 users), and under Settings, Authentication, the **One-time PIN** login method.
3. An Access service token named exactly `orc-plane-tests`. Save its Client ID and Client Secret as the organisation secrets `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET`, available to all the organisation's repositories, this one included. The README notes the expiry chosen; to rotate, make a new token with the same name, delete the old one, update the two secrets, and run any apply to dev or staging, which moves the shared policy to the new token.
4. An account API token, on that account only, with `Workers Scripts: Edit`, `Access: Apps and Policies: Edit`, `Access: Service Tokens: Read` and `Access: Organizations, Identity Providers, and Groups: Read`, saved as the repository secret `CLOUDFLARE_API_TOKEN`; the account id as the secret `CLOUDFLARE_ACCOUNT_ID`.
   If a run shows a 403, the README records the extra permission it needed (for example `Account Settings: Read`).
5. The owner's email, the one to receive one-time PINs for dev and staging, as the repository secret `ACCESS_OWNER_EMAIL` (a secret, so Actions masks it in this public repository's logs).
6. A second GitHub App, `agentic-orc-plane-reader` or similar, owned by `agentic-orc-farm`, with only `Actions: Read` (and the `Metadata: Read` GitHub adds), no webhook, installed on all the organisation's repositories.
   Its Client ID as the repository variable `PLANE_READER_CLIENT_ID`, its private key as the secret `PLANE_READER_PRIVATE_KEY`.
   It is not the driver's App: that one can write to every repository, and its key stays on the owner's machine (the orchestrator's ADR 0008).
7. Branch protection on `main`, and only the owner and the driver's App with write access, because write access is what lets someone dispatch a workflow that holds the secrets.
8. The bootstrap above: before this pull request's first live run, copy `.github/workflows/acceptance.yml` from the reviewed commit to `main`.

This repository is public while the organisation is on GitHub Free, so its Actions logs are public: the shim logs Worker names and addresses, never tokens, account ids, the owner's email or response bodies.

## The README

Besides the owner steps and the `## Kinds` section (AC13):

- `## Private environments` (AC34): `prod` is public; `dev` and `staging` are behind Cloudflare Access. A project's `make smoke` and `make acceptance` reach them by sending `CF-Access-Client-Id: $CF_ACCESS_CLIENT_ID` and `CF-Access-Client-Secret: $CF_ACCESS_CLIENT_SECRET` on every request, from the organisation secrets of those names; the project holds no other Cloudflare credential. A request without them gets a redirect to the login page, not the site. The owner opens them in a browser with the email in `ACCESS_OWNER_EMAIL` and a one-time PIN.
- How the plane is tested: `ci.yml` checks every push without secrets; the live criteria run only in the `acceptance` workflow, dispatched with a `commit` for a reviewed commit; fork pull requests are not taken.
- The two limits on artefacts: they expire with the project's retention setting (90 days by default), and the newest matching artefact for the commit wins.

## The cleanup runbook

`docs/cleanup.md`, one section per kind.

`## static-site`:

- How to find a project's Workers: list the Workers whose names start with `<repo>-` and end with `-<env>`, then keep those whose deployments' marker says `project=<owner/repo>`, because the prefix alone also matches other projects such as `<repo>-admin`.
- Remove one with `wrangler delete --name <worker>` or the dashboard; for dev and staging, remove its Access application first (below).
- The two owner-check refusals: a Worker with no plane marker (delete it if it is not wanted, or rename the component), and the rare race in which two colliding projects both deployed one Worker (the newest marker wins; delete the Worker and let the rightful project apply again).
- The fixture Workers `cloudflare-fixture-web-prod` and `cloudflare-fixture-web-dev` belong to this repository's `acceptance` workflow, which recreates them.

`### Access` (AC14):

- A private Worker's application is the one named `<worker>` whose destination is that Worker (Zero Trust, Access, Applications). Delete it before or with the Worker; an application left for a deleted Worker protects nothing, and the next apply of a new Worker of that name makes a new one.
- Two applications for one Worker, or two policies with one of the plane's names, make the plane refuse; delete the extra one (either is fine: they are the same) and apply again.
- The shared policies `orc-plane-service-token` and `orc-plane-owner` are used by every private Worker. Delete them only when no application uses them; the next private apply recreates them.
- The service token `orc-plane-tests` and the one-time PIN login method are the owner's (README steps 2 and 3); the plane never creates or deletes them.

## Decision records

- `docs/adr/0001-resource-names.md`: Workers are `<repo>-<component>-<env>` on `workers.dev`, refused rather than rewritten when they do not fit, and only for projects in the plane's own organisation; a name two projects can reach is held by the first, and the marker's owner check refuses the second. Access applications take their Worker's name.
- `docs/adr/0002-reading-project-artefacts.md`: a read-only organisation GitHub App, a per-run token for one repository, and artefacts found by name and commit from runs of the project itself; secrets only in workflows started by `workflow_dispatch`.
- `docs/adr/0003-a-stateless-shim.md`: a Python shim over a pinned wrangler that compares desired with observed state, a deployment marker as the only record of what runs, and `result.json` version 1 as the contract with the driver.
- `docs/adr/0004-access-for-private-environments.md`: one `worker`-destination Access application per private Worker, two shared reusable policies found by name, the owner by email and one-time PIN, and the order that keeps a new Worker unreachable until its application exists.

## What I could not verify

- **The `worker` destination.** Cloudflare documents `{"type": "worker", "worker_id": ...}` for self-hosted applications, but not which id `worker_id` is (I expect the id the Workers API returns for the Worker, `GET /accounts/{account}/workers/workers/{name}`, which may or may not equal the script's `tag`), nor what `domain`, which the schema marks required, must hold for such an application. If the destination cannot be made to work as documented, the engineering agent reports a design defect naming the fallback in ADR 0004 (a hostname application for `<worker>.<subdomain>.workers.dev`, created before the first deploy), rather than switching silently; the criteria stay the same.
- **That a Worker deployed with `workers_dev: false` and `preview_urls: false` answers at no address.** Cloudflare's workers.dev page says turning workers.dev off does not turn off "Version URLs, Preview URLs, or Deployment URLs"; `preview_urls: false` turns off the first two, and I could not find what a "Deployment URL" is. The `worker` destination covers every address of the Worker once the application exists; AC37 checks the main address through the window.
- How long a new Access application takes to apply at the edge (the 30-second wait; AC37 tests it).
- The exact names of the API token's Access permissions (step 4).
- That a request without the headers gets a redirect rather than a 403; the criteria need only "not 200".
- That `wrangler deploy --message` fills the deployment's `annotations["workers/message"]`. The API reference lists the annotation; that wrangler writes the message there I take from wrangler's documentation. If it does not, use `--tag` and the versions API instead; the criteria do not change.
- How many deployments the deployments API lists (the owner check reads the newest marker among them). I believe it is the most recent ten; the runbook covers a Worker rolled back by hand more times than that.
- The fork filter relies on the artefact's `workflow_run.repository_id` and `workflow_run.head_repository_id`, which GitHub's REST reference lists; and that a `pull_request` run's `workflow_run.head_sha` is the pull request's head commit, which the `fixture` artefact depends on.
- That organisation secrets reach private repositories on GitHub Free. I believe they reach only public ones on Free; this repository is public, but a private project would not get `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET` until the organisation's plan changes or they are set per repository.
- How long a new `workers.dev` address takes to answer; AC17 and AC36 allow 120 seconds.
- The current major versions of `actions/checkout`, `astral-sh/setup-uv`, `actions/setup-node`, `actions/upload-artifact` and `actions/create-github-app-token` (v3, with `client-id` and `repositories` inputs): the engineering agent pins the latest at set-up.
