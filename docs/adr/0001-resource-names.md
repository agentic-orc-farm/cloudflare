# 0001: How the plane names what it creates

Status: proposed
Date: 2026-10-23

## Context

The plane keeps no state, so it finds everything it created by name.
A name is therefore an address and a key at once: changing the rule later orphans every existing Worker and changes every project's URL.
The request says a Worker is "named after the project and environment".
A project's `deploy.yaml` may list more than one `static-site` component, and a Worker name must be at most 63 characters of lowercase letters, digits and dashes, because it becomes a DNS label on `workers.dev`.
GitHub repository names may contain uppercase letters, dots and underscores, and run to 100 characters.

## Decision

- A component's Worker is `<repo>-<component>-<env>`, where `<repo>` is the project's repository name without its owner.
- Its address is `https://<worker>.<account subdomain>.workers.dev`. No custom domains until a request needs one.
- The plane deploys only projects in its own organisation (`PLANE_ORG`, set from the repository's owner), so the repository name alone is unique.
- A repository name with characters outside `[a-z0-9-]`, or a Worker name over 63 characters, is refused with a message naming the rule. Nothing is rewritten or truncated: `my.site` and `my-site`, or two long names, would otherwise share a Worker.
- Later kinds and the Access objects of increment 2 follow the same pattern, so everything for one project and environment can be found by the prefix `<repo>-` and the suffix `-<env>`.

## Alternatives

- **`<repo>-<env>`, as the request words it.** Two components of one project would deploy over each other; refusing a second component would make `deploy.yaml` less than it promises.
- **Include the owner (`<owner>-<repo>-...`).** Unique across organisations, but uses up the 63 characters for no gain while the plane serves one organisation.
- **Rewrite and truncate to fit, with a hash suffix.** Always succeeds, but the name no longer tells a person whose Worker it is, and the runbook gets harder.

## Consequences

- Renaming a repository or a component creates a new Worker and leaves the old one; the runbook says how to remove it.
- A project with a long repository name must use short component names.
- This repository's own CI fixture is `cloudflare-site-prod`, which no project can collide with.

## What enforces it

- Unit tests of the naming function, and acceptance criteria AC5, AC8 and AC9 (the name, and the refusals).
- AC15 and AC17 check the address of a real Worker.
