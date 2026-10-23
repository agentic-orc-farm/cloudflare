# 0001: How the plane names what it creates, and who owns a name

Status: proposed
Date: 2026-10-23

## Context

The plane keeps no state, so it finds everything it created by name.
A name is therefore an address and a key at once: changing the rule later orphans every existing Worker and changes every project's URL.
The request says a Worker is "named after the project and environment".
A project's `deploy.yaml` may list more than one `static-site` component, and a Worker name must be at most 63 characters of lowercase letters, digits and dashes, because it becomes a DNS label on `workers.dev`.
GitHub repository names may contain uppercase letters, dots and underscores, and run to 100 characters.
Repository and component names may both contain dashes, so joining them with a dash is ambiguous: project `shop` with component `admin-site` and project `shop-admin` with component `site` both give `shop-admin-site-prod`.
Without a guard, the second project's apply would silently replace the first project's site.

## Decision

- A component's Worker is `<repo>-<component>-<env>`, where `<repo>` is the project's repository name without its owner.
- Its address is `https://<worker>.<account subdomain>.workers.dev`. No custom domains until a request needs one.
- The plane deploys only projects in its own organisation (`PLANE_ORG`, set from the repository's owner).
- A repository name with characters outside `[a-z0-9-]`, or a Worker name over 63 characters, is refused with a message naming the rule. Nothing is rewritten or truncated: `my.site` and `my-site`, or two long names, would otherwise ask for one Worker.
- **Every Worker records its owner.** The deployment marker (ADR 0003) starts `orc project=<owner/repo>`. A Worker's owner is the project in the newest marked deployment the deployments API lists.
- **A name is held by the first project to deploy it.** A plan or apply for a Worker that exists and belongs to another project is refused, before anything is deployed, with the line `<component>: Worker <worker> belongs to <owner/repo>` and the advice to rename the component. A Worker that exists with no plane marker is refused the same way (`was not deployed by the plane`), because the plane cannot tell whose it is.
- A project's Workers are found by listing names that start with `<repo>-` and end with `-<env>` and keeping those whose marker names the project. The prefix alone is not enough, because it also matches projects such as `<repo>-admin`.
- A private Worker's Access application is named `<worker>` and found by its `worker` destination, not by name (ADR 0004). It needs no owner of its own: the Worker's owner check runs first, so the plane never touches the application of another project's Worker.
- The two shared Access policies are `orc-plane-service-token` and `orc-plane-owner`, and the service token the owner makes is `orc-plane-tests`. The `orc-plane-` prefix marks what the plane uses; renaming any of them orphans it.
- Later kinds follow the same naming pattern and carry the owning project where Cloudflare lets them (in a name, tag or description), and are checked for ownership the same way.

## Alternatives

- **`<repo>-<env>`, as the request words it.** Two components of one project would deploy over each other; refusing a second component would make `deploy.yaml` less than it promises.
- **A separator neither part may contain, such as `--`** (`<repo>--<component>--<env>`, with `--` forbidden in repository and component names). The name itself would be unambiguous, but it spends 4 more of the 63 characters, adds a rule the driver's `deploy.yaml` check does not have, and a label with `--` in its third and fourth characters (for example a two-letter repository) is reserved in DNS for IDNA, which I could not show Cloudflare accepts. It also would not protect against a Worker made by hand or by another tool under a plane name; the owner check does both.
- **Include the owner (`<owner>-<repo>-...`).** Unique across organisations, but uses up the 63 characters for no gain while the plane serves one organisation, and does not remove the dash ambiguity.
- **Rewrite and truncate to fit, with a hash suffix.** Always succeeds, but the name no longer tells a person whose Worker it is, and the runbook gets harder.

## Consequences

- Two projects that reach one name cannot both deploy that component; the second is told which project holds the name and renames its component. In one organisation that is rare and visible, not silent.
- The owner check depends on the marker's history. A Worker rolled back by hand more times than the deployments API lists would be refused as "not deployed by the plane"; the runbook says how to recover.
- Two colliding projects whose very first applies race each other could both see no Worker and both deploy, because the concurrency group is per project. The runbook says how to spot and fix it.
- Renaming a repository or a component creates a new Worker and leaves the old one; the runbook says how to remove it.
- A project with a long repository name must use short component names.
- This repository's own fixtures are `cloudflare-fixture-web-prod` and `cloudflare-fixture-web-dev`; the `acceptance` workflow also asks for the prod name as the project `cloudflare-fixture` with component `web`, to show the refusal.

## What enforces it

- Unit tests of the naming function and of the owner check (another project, no marker, a rollback after a marked deployment).
- Acceptance criteria AC5, AC9, AC24 and AC31 (the name and the refusals), AC17, AC19, AC35 and AC36 (the address of a real Worker, public and private), AC39 and AC40 (the Access objects' names), and AC29 and AC30 (a plan and an apply onto a Worker another project owns are refused, and its active deployment does not change).
