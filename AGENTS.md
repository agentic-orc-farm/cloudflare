# cloudflare

The Cloudflare plane for `agentic-orc-farm`: a stateless Python shim, `cf-plane`, over a pinned wrangler, run by the `deploy` workflow.
The design is `docs/design/create-the-cloudflare-plane-for-the.md`; the decisions are in `docs/adr/`.

## Set up and check

- Set up: `make setup` (`uv sync --locked` and `npm ci`).
- `make check`: `ruff check`, `ruff format --check`, `pyright`, `lint-imports`, `zizmor .github/workflows`, `pip-audit` over the locked runtime dependencies, and `npm audit --omit=dev --audit-level=high`.
- `make test`: `pytest -n auto tests/unit`, with Cloudflare and GitHub faked through `httpx.MockTransport` and wrangler replaced by a scripted fake executable. No credentials, no network.
- `make acceptance`: `pytest tests/acceptance`. Offline criteria always run; live ones only with `ACCEPTANCE_LIVE=1`, which only the `acceptance` workflow sets.
- `make package` and `make smoke ENV=<env>` print that they do nothing: the plane is never deployed and has no environments.
- `make fixture-site COMMIT=<sha> OUT=<dir>` packages the fixture project for `ci.yml`.
- Before committing, `make check`, `make test` and `make acceptance` pass.

## Standards

This project follows the owner's standards, version 2; the copies are in `docs/standards/`.
Read `PYTHON-BASE.md` and `PYTHON-CLI.md` (including the agent-facing section) before writing Python, and `GITHUB.md` before touching workflows.
Deliberate differences for this project, from the design:

- Actions are pinned to a full commit SHA with the version in a comment, stricter than `GITHUB.md` section 7, because any action here could read the deploy token. zizmor enforces it.
- Not `PYTHON-WORKFLOW.md`: the shim keeps no state, journal or approvals; the driver holds the approvals.
- `npm audit --audit-level=high` blocks `make check`. If it blocks unrelated changes too often, lower it to a report and say so here.

## Conventions

- Python 3.13, uv only, `src/cf_plane/`. Commands are declared as data in `cli.py`.
- Layers, checked by import-linter: `cli` above `cloudflare | artefacts | wrangler` above `changes` above `static_site | access` above `contract`. The pure modules (`contract`, `static_site`, `access`, `changes`) may not import `httpx` or `subprocess`.
- Every outside call has a timeout: 30 seconds per HTTP request, 120 seconds per artefact download, 300 seconds for wrangler (run in its own process group). No automatic retries.
- Never log or write to `result.json` a token, the account id, `ACCESS_OWNER_EMAIL` or an Access response body: this repository's Actions logs are public.
- Workflows: inputs reach `run:` only through `env:`; only `deploy.yml` and `acceptance.yml` use secrets, and both are started only by `workflow_dispatch`; `ci.yml` never sees a secret; `pull_request_target` is never used.
- wrangler is pinned to an exact version in `package.json` and `package-lock.json`, which hold nothing else.
- `tests/acceptance/` belongs to the test agent, including `tests/acceptance/fixture-site/`; `docs/design/` and `deploy.yaml` change only through the design. Do not edit them.
- Commits: `area: what changed`, no AI trailers (`GITHUB.md` section 3).
