# 0004: Cloudflare Access in front of dev and staging

Status: proposed
Date: 2026-10-23

## Context

Only prod is public (the orchestrator's ADR 0011). A project's dev and staging Workers must sit behind a login, its tests must reach them with the organisation's one read-only Access service token (`CF_ACCESS_CLIENT_ID`, `CF_ACCESS_CLIENT_SECRET`), and the owner wants to open them in a browser.
wrangler does not manage Access, so the shim calls the Access API itself.
The plane keeps no state, so it must find every Access object again on the next run, and a second apply must not duplicate any of them.
A Worker must never be reachable before its Access application exists.
Every project's private Workers are let in by the same two parties, so whatever admits them is shared, and a change to it (a rotated token, a new email) should reach every Worker at once.

## Decision

- **One self-hosted Access application per private Worker**, named `<worker>`, with exactly one destination `{"type": "worker", "worker_id": <the Worker's id>}`. It is found by that destination, not by name. A `worker` destination protects every address of the Worker: workers.dev, previews and any later route.
- **Two shared reusable policies, found by exact name**, created by the shim if missing and updated in place if they differ:
  - `orc-plane-service-token`: decision `non_identity` (Service Auth), including exactly the service token named `orc-plane-tests`.
  - `orc-plane-owner`: decision `allow`, including exactly the email in the repository secret `ACCESS_OWNER_EMAIL`.
- Each application uses exactly those two policies, allows only the account's one-time PIN login method, redirects to it directly, and is hidden from the App Launcher.
- **The owner makes, once, what the plane only reads**: the Zero Trust organisation, the one-time PIN login method and the service token `orc-plane-tests`. The shim refuses, naming the README step, when any is missing or doubled.
- **Order.** A new private Worker is first deployed with workers.dev and previews off, so it exists at no address; then its application is created; then, after 30 seconds for Access to take effect, workers.dev is turned on through the script subdomain API. An existing Worker's application is made or fixed before the Worker is deployed again.
- More than one application for a Worker, or more than one policy with one of the plane's names, is refused, not repaired: the plane cannot tell which one a person meant to keep.
- prod has no Access objects.

## Alternatives

- **A hostname application for `<worker>.<subdomain>.workers.dev`.** Can be created before the Worker exists, so the order is simpler (application first, then deploy). But it covers one hostname only, so previews and any later route are open unless turned off elsewhere, and I could not confirm that the API accepts a `workers.dev` hostname. This is the fallback if the `worker` destination does not work as documented; switching to it is a design change, reported by the engineering agent, not made silently. The criteria stay the same.
- **One account-wide `all_workers` application, with a bypass application for each prod Worker.** One object instead of one per Worker, and new Workers are private by default. But it makes every Worker in the account private, including ones the plane did not make, and a prod Worker is public only once its bypass exists, so a failed apply leaves prod private. It reverses the request's default (one application per private Worker) for a gain the request does not ask for.
- **Inline policies on each application.** No shared objects, but a rotated service token or a new email needs every application updated, and an application could drift from the others unnoticed.
- **One policy for both.** Not possible: a service token needs a Service Auth (`non_identity`) decision, and an email an `allow` decision.
- **The shim creates the service token and the login method.** Fewer owner steps, but the token's secret would pass through a public repository's run and would have to be written to organisation secrets, which needs a further, wider credential.
- **The owner's email as a repository variable.** Simpler, but variables are not masked, and this repository's logs are public.

## Consequences

- The deploy token needs Access permissions as well as `Workers Scripts: Edit` (README step 4).
- Rotating the service token or changing the owner's email takes one apply to any private environment, and fixes every project's private Workers at once.
- The first apply of a new private Worker takes about 30 seconds longer than later ones.
- Two projects' first private applies racing each other could both create a shared policy, because their concurrency groups differ; the next run refuses with both names, and the runbook says to delete either.
- Deleting a private Worker leaves its application; the runbook says to delete both.
- Requests without the headers are redirected to the login page, so projects' tests must send them on every request to dev and staging; the README says how.

## What enforces it

- Unit tests of `access.py` and `changes.py` with a faked Access API: find by destination and by name, create, update in place, refuse duplicates, refuse missing owner-made objects, and the apply order as data (no step that makes a Worker reachable before its application exists, and the wait after creating one).
- AC37: a request without the headers never gets a 200 through the whole apply that creates the dev Worker. AC36 and AC38: with the headers 200, without them not. AC39 and AC40: exactly one application and one of each policy, with the right contents, after one apply and after two. AC43: prod has no application.
- That the owner-made objects are made as the README says can only be reviewed.
