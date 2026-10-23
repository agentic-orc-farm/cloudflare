# cloudflare

The Cloudflare plane for the `agentic-orc-farm` organisation: the one repository that provisions and deploys projects onto Cloudflare, so that projects hold no Cloudflare configuration, tooling or deploy credentials.

A project's driver dispatches this repository's `deploy` workflow with the project, a commit, an environment, a mode (`plan` or `apply`) and the project's `deploy.yaml` components for this plane.
A small Python shim, `cf-plane`, turns each component into a wrangler configuration, runs a pinned wrangler, and writes `result.json`.
It keeps no state of its own. The design is in `docs/design/` and the decisions in `docs/adr/`.

## Run it locally

You need [uv](https://docs.astral.sh/uv/) and Node 24 (wrangler 4 needs Node 22 or later).

```sh
make setup                 # uv sync --locked, and npm ci for the pinned wrangler
uv run cf-plane --help     # the shim's commands
```

Nothing local needs a Cloudflare credential: the owner's machine never holds the deploy token.

## Check it

| Command | What it runs |
|---|---|
| `make check` | ruff, ruff format, pyright, import-linter, zizmor over the workflows, pip-audit and `npm audit` |
| `make test` | the unit tests, with Cloudflare, GitHub and wrangler faked; no credentials, no network |
| `make acceptance` | the acceptance criteria in `tests/acceptance/`: the offline ones always, the live ones only with `ACCEPTANCE_LIVE=1` |
| `make package` | nothing: the plane is never deployed, so it has no artefact |
| `make smoke ENV=<env>` | nothing: the plane has no environments |

CI (`.github/workflows/ci.yml`) runs `make check`, `make test` and `make acceptance` on every pull request and push to `main`, with no secrets, and packages the fixture site (`make fixture-site`) as the artefact `fixture-site`.
The live acceptance criteria deploy to Cloudflare, so they run only in the `acceptance` workflow (`.github/workflows/acceptance.yml`), dispatched with a `commit` for a reviewed commit.
