# 0002: How the plane reads a project's artefacts, and which runs hold secrets

Status: proposed
Date: 2026-10-23

## Context

`apply` must deploy exactly the artefact the project's CI built for a commit (build once, promote: `GITHUB.md` section 7).
The artefact lives in another repository's Actions storage.
The plane's own `GITHUB_TOKEN` cannot read another private repository, and the organisation's repositories are public only while it is on GitHub Free.
The driver's GitHub App can write to every repository and its key lives on the owner's machine, so it must not be a secret here.
ADR 0012 of the orchestrator left this open.

The secrets that read artefacts and deploy (the App key, the account-wide Cloudflare token) are the most powerful in the organisation.
The orchestrator's flow says "Deploy once": CI checks every push, and a deploy happens only for a commit that passed review.
That applies to this repository's own live tests, which deploy.

## Decision

- A second GitHub App, owned by the organisation, with only `Actions: Read` and `Metadata: Read`, no webhook, installed on all the organisation's repositories.
  Its Client ID is the repository variable `PLANE_READER_CLIENT_ID`; its private key is the secret `PLANE_READER_PRIVATE_KEY` of this repository only.
- For `apply` only, the workflow mints an installation token with `actions/create-github-app-token`, limited to the one project repository and to `actions: read`. It expires within an hour.
- The shim finds the artefact by the component's `artefact` name and the commit (`workflow_run.head_sha`), skipping expired ones and ones from runs started from a fork (`workflow_run.head_repository_id` differs from `workflow_run.repository_id`), and takes the newest.
  It does not require the CI run to have passed: the driver asks for a deploy only once CI is green for the commit.
- `plan` reads no artefacts and mints no token, so it works before a commit has been packaged, as at the design gate.
- **Secrets only in dispatched runs.** Only `deploy.yml` and `acceptance.yml` reference secrets, and both are started only by `workflow_dispatch`. `ci.yml`, which runs on every `pull_request` and `push`, has no secrets; `pull_request_target` is never used.
- **Live tests for a reviewed commit.** The live acceptance criteria run only in `acceptance.yml`, dispatched on `main` with a `commit` input, so the definition that receives the secrets is a merged one. The driver dispatches it only for a commit that passed review and whose CI is green, as it does for a project's deploy. The plane's fixture artefact comes from `ci.yml`, without secrets, like any project's.

## Alternatives

- **A fine-grained personal access token.** Simpler to create, but long-lived, tied to a person, and it must be rotated.
- **Projects publish to a release or a bucket.** Changes every project's CI and the contract.
- **The plane's `GITHUB_TOKEN`.** Fails for the first private project.
- **`actions/download-artifact` in the workflow.** Works with the same token, but moves the lookup out of the shim, where the live tests cannot exercise it as one command.
- **Live tests in pull request CI.** Every push would deploy, and a branch's unreviewed code would run with the deploy token. Rejected by the owner.
- **Live tests behind a GitHub environment with required reviewers.** Keeps them in pull request CI but asks the owner to approve each run by hand, which the driver cannot do and which still runs on every push.
- **Dispatching on the pull request's branch.** Would run the branch's own copy of the workflow, but GitHub still requires the file on the default branch, and the secrets would reach a definition nobody has merged.

## Consequences

- The owner creates and installs one more App, once.
- Promoting a commit older than the project's artefact retention (90 days by default) fails with a message saying so.
- The plane trusts the driver to have checked CI before asking for an apply.
- A pull request's live criteria have evidence only once the driver has dispatched `acceptance` for its reviewed commit; CI on the pull request shows the offline criteria. The evidence is a successful run named `acceptance <commit>`.
- Write access to this repository is what lets someone dispatch a workflow with the secrets, so only the owner and the driver's App have it, and `main` is protected.
- GitHub dispatches only workflows on the default branch, so the first pull request needs `acceptance.yml` copied to `main` by the owner before its live criteria can run. After that, changes to the workflow are merged before they run with secrets.
- A change to `acceptance.yml` runs with the secrets only after it is merged, so its own pull request's live run still uses the previous definition.

## What enforces it

- AC33: no workflow started by `pull_request`, `pull_request_target` or `push` contains `secrets.`, and the two that do are started only by `workflow_dispatch`. AC32: `acceptance.yml` takes exactly one input, `commit`, and checks out that commit.
- `zizmor` in `make check` flags workflow permissions wider than declared and dangerous triggers; each workflow's `permissions:` is `contents: read`.
- AC16 (a plan with no token) and AC17 and AC22 (an apply that finds, or fails to find, the artefact) exercise the artefact path.
- The App's permissions, and who has write access, can only be reviewed on GitHub; the README lists them.
