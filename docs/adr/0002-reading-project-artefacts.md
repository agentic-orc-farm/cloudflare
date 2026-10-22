# 0002: How the plane reads a project's artefacts

Status: proposed
Date: 2026-10-23

## Context

`apply` must deploy exactly the artefact the project's CI built for a commit (build once, promote: `GITHUB.md` section 7).
The artefact lives in another repository's Actions storage.
The plane's own `GITHUB_TOKEN` cannot read another private repository, and the organisation's repositories are public only while it is on GitHub Free.
The driver's GitHub App can write to every repository and its key lives on the owner's machine, so it must not be a secret here.
ADR 0012 of the orchestrator left this open.

## Decision

- A second GitHub App, owned by the organisation, with only `Actions: Read` and `Metadata: Read`, no webhook, installed on all the organisation's repositories.
  Its Client ID is the repository variable `PLANE_READER_CLIENT_ID`; its private key is the secret `PLANE_READER_PRIVATE_KEY` of this repository only.
- For `apply` only, the workflow mints an installation token with `actions/create-github-app-token`, limited to the one project repository and to `actions: read`. It expires within an hour.
- The shim finds the artefact by the component's `artefact` name and the commit (`workflow_run.head_sha`), skipping expired ones and ones from runs started from a fork (`workflow_run.head_repository_id` differs from `workflow_run.repository_id`), and takes the newest.
  It does not require the CI run to have finished or to have passed: the newest matching artefact wins even if its run later failed. The driver asks for a deploy only once CI is green for the commit, so a failed run's artefact is deployed only if the driver asks for that commit anyway.
- `plan` reads no artefacts and mints no token, so it works before a commit has been packaged, as at the design gate.

## Alternatives

- **A fine-grained personal access token.** Simpler to create, but long-lived, tied to a person, and it must be rotated.
- **Projects publish to a release or a bucket.** Changes every project's CI and the contract.
- **The plane's `GITHUB_TOKEN`.** Fails for the first private project.
- **`actions/download-artifact` in the workflow.** Works with the same token, but moves the lookup out of the shim, where this repository's CI cannot exercise it as one command.

## Consequences

- The owner creates and installs one more App, once.
- Promoting a commit older than the project's artefact retention (90 days by default) fails with a message saying so.
- The plane trusts the driver to have checked CI before asking for an apply; the plane itself would deploy an artefact from a run that failed after uploading it.
- A pull request from a branch of this repository runs that branch's code in the CI `acceptance` job with this repository's secrets, before any review: the account-wide `Workers Scripts: Edit` token and the App key that can read every project's Actions. So anyone who can push a branch here can change any Worker in the account and read any project's artefacts. Only the owner and the driver's App push here, and branch protection keeps it so; the README says this beside the note that fork pull requests get no secrets.
- This repository's CI depends on artefacts being listed while their run is still in progress (documented for `upload-artifact` v4 and later).

## What enforces it

- The App's permissions can only be reviewed on GitHub; the README lists them.
- `zizmor` in `make check` flags workflow permissions wider than declared; the workflow's `permissions:` is `contents: read`.
- AC16 (a plan with no token) and AC17 and AC22 (an apply that finds, or fails to find, the artefact) exercise the path.
