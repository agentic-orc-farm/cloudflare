# cloudflare

The Cloudflare plane for the `agentic-orc-farm` organisation: the one repository that provisions and deploys projects onto Cloudflare, so that projects hold no Cloudflare configuration, tooling or deploy credentials.

A project's driver dispatches this repository's `deploy` workflow with the project, a commit, an environment, a mode (`plan` or `apply`) and the project's `deploy.yaml` components for this plane.
A small Python shim, `cf-plane`, turns each component into a wrangler configuration, runs a pinned wrangler, sets up Cloudflare Access for dev and staging, and writes `result.json`.
It keeps no state of its own: Cloudflare is the record of what exists, and a marker on each deployment records which project and commit it came from.
The design is in `docs/design/` and the decisions in `docs/adr/`.

## The `deploy` workflow

`.github/workflows/deploy.yml`, started only by `workflow_dispatch`, with these inputs, all required:

| Input | Value |
|---|---|
| `project` | `owner/repo`, where the owner is this repository's organisation and the repository name is lowercase letters, digits and dashes |
| `commit` | the full 40-character sha |
| `env` | `dev`, `staging` or `prod` |
| `mode` | `plan` reports what it would create or change and changes nothing; `apply` makes the changes |
| `components` | a JSON list of the project's `deploy.yaml` entries for this plane, each with exactly `name`, `kind`, `plane` and `artefact` |

Either way the run uploads `result.json` as the artefact `result`:

```json
{
  "schema_version": 1,
  "components": [{"name": "site", "url": "https://example-site-dev.acme.workers.dev"}],
  "summary": "dev plan for agentic-orc-farm/example at <commit>\nAccess policy orc-plane-service-token: unchanged\nAccess policy orc-plane-owner: unchanged\nsite: would create Worker example-site-dev, would create Access application example-site-dev"
}
```

The run's conclusion is the signal; `result.json` is the detail.
On a refusal `components` is empty and the summary says what is wrong and what would fix it.
Running the same apply twice is safe: it creates what is missing, updates what differs, and never duplicates.
Runs for one project and environment queue behind each other; GitHub keeps only one pending run per group, so a driver treats a cancelled run as "ask again".

An apply deploys exactly the artefact the project's CI uploaded for the commit.
Two limits: artefacts expire with the project's retention setting (90 days by default), so promoting an older commit fails with a message saying so; and if several runs for the commit uploaded the artefact, the newest one wins.
A plan reads no artefacts, so it works before the commit's CI has packaged anything.

## Kinds

The kinds the plane offers:

- `static-site`: a Worker with static assets and no code, named `<repo>-<component>-<env>` (at most 63 characters, refused rather than truncated), at `https://<worker>.<account subdomain>.workers.dev`.
  The artefact is served as it is; a `404.html` in it is served, with status 404, for any path that does not exist.
  Preview URLs are always off.
  `prod` is public; `dev` and `staging` sit behind Cloudflare Access (below).

A Worker name belongs to the first project that deploys it: a project asking for a Worker another project holds is refused, and is told to rename its component.

## Private environments

`prod` is public: anyone can open it.
`dev` and `staging` are not public: they sit behind Cloudflare Access, with one Access application per Worker.

A project's `make smoke` and `make acceptance` reach dev and staging by sending these two headers on every request:

```
CF-Access-Client-Id: $CF_ACCESS_CLIENT_ID
CF-Access-Client-Secret: $CF_ACCESS_CLIENT_SECRET
```

`CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET` are organisation secrets holding the one read-only Access service token, `orc-plane-tests`, available to every repository of the organisation; the project holds no other Cloudflare credential.
A request without them is sent to the login page, not the site.
The owner opens dev and staging in a browser with the email in `ACCESS_OWNER_EMAIL` and a one-time PIN.
Organisation secrets reach only public repositories on GitHub Free; a private project needs the organisation on a paid plan, or the two secrets set on the repository itself.

## Owner set-up, once

The plane cannot do these for itself.

1. A Cloudflare account with a `workers.dev` subdomain chosen (Workers & Pages, once).
2. A Zero Trust organisation on that account (the free plan covers up to 50 users), and under Settings, Authentication, the **One-time PIN** login method.
3. An Access service token named exactly `orc-plane-tests`. Save its Client ID and Client Secret as the organisation secrets `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET`, available to all the organisation's repositories, this one included.
   Note the expiry chosen here: (not yet set).
   To rotate: make a new token with the same name, delete the old one, update the two secrets, and run any apply to dev or staging, which moves the shared policy to the new token.
4. An account API token, on that account only, with `Workers Scripts: Edit`, `Access: Apps and Policies: Edit`, `Access: Service Tokens: Read` and `Access: Organizations, Identity Providers, and Groups: Read`, saved as the repository secret `CLOUDFLARE_API_TOKEN`; the account id as the repository secret `CLOUDFLARE_ACCOUNT_ID`.
   If a run shows a 403, record here the extra permission it needed.
5. The owner's email, the one to receive one-time PINs for dev and staging, as the repository secret `ACCESS_OWNER_EMAIL` (a secret, so Actions masks it in this public repository's logs).
6. A GitHub App owned by `agentic-orc-farm` (for example `agentic-orc-plane-reader`), with only `Actions: Read` (and the `Metadata: Read` GitHub adds), no webhook, installed on all the organisation's repositories.
   Its Client ID as the repository variable `PLANE_READER_CLIENT_ID`, its private key as the repository secret `PLANE_READER_PRIVATE_KEY`.
   It is not the driver's App, which can write to every repository.
7. Branch protection on `main`, and only the owner and the driver's App with write access, because write access is what lets someone dispatch a workflow that holds the secrets.
8. Before the first live acceptance run, copy `.github/workflows/acceptance.yml` from the reviewed commit to `main`: GitHub dispatches only workflows that are on the default branch.

The secrets `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `ACCESS_OWNER_EMAIL` and `PLANE_READER_PRIVATE_KEY` belong to this repository only.
This repository is public, so its Actions logs are public: the shim logs Worker names and addresses, never tokens, the account id, the owner's email or Access response bodies.

## How the plane is tested

- `ci.yml` checks every pull request and every push to `main` without secrets: `make check`, `make test`, and the offline acceptance criteria. It also packages the fixture site as the artefact `fixture-site` for the commit.
- The live acceptance criteria deploy to Cloudflare, so they run only in the `acceptance` workflow (`.github/workflows/acceptance.yml`), dispatched with a `commit` for a reviewed commit whose CI is green. The run is named `acceptance <commit>`.
- Fork pull requests are not taken: no workflow they can start sees a secret.
- The live criteria deploy this repository as its own fixture project: `cloudflare-fixture-web-prod` (public) and `cloudflare-fixture-web-dev` (behind Access). Do not dispatch `deploy` for `agentic-orc-farm/cloudflare` by hand: it could overlap an acceptance run.

## Run it locally

You need [uv](https://docs.astral.sh/uv/) and Node 24 (wrangler 4 needs Node 22 or later).

```sh
make setup                 # uv sync --locked, and npm ci for the pinned wrangler
uv run cf-plane --help     # the shim's commands
uv run cf-plane wrangler-config --project agentic-orc-farm/example --env prod \
  --component '{"name":"site","kind":"static-site","plane":"cloudflare","artefact":"site"}' --assets ./site
```

`wrangler-config` prints a component's wrangler configuration with no credentials and no network.
Nothing local needs a Cloudflare credential: the owner's machine never holds the deploy token.

## Check it

| Command | What it runs |
|---|---|
| `make check` | ruff, ruff format, pyright, import-linter, zizmor over the workflows, pip-audit and `npm audit` |
| `make test` | the unit tests, with Cloudflare, GitHub and wrangler faked; no credentials, no network |
| `make acceptance` | the acceptance criteria in `tests/acceptance/`: the offline ones always, the live ones only with `ACCEPTANCE_LIVE=1` |
| `make package` | nothing: the plane is never deployed, so it has no artefact |
| `make smoke ENV=<env>` | nothing: the plane has no environments |

To remove what the plane made, see `docs/cleanup.md`.
