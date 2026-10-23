# Cleaning up after the plane

The plane keeps no state, so removing something it made is a matter of finding it by name in Cloudflare and deleting it.
One section per kind.

## static-site

### Finding a project's Workers

A component's Worker is `<repo>-<component>-<env>`.
To find a project's Workers, list the Workers (Workers & Pages, or `GET /accounts/{account}/workers/scripts`) whose names start with `<repo>-` and end with `-<env>`, then keep only those whose deployments carry the marker `orc project=<owner>/<repo>` (Deployments tab, the deployment message).
The prefix alone is not enough: `<repo>-` also matches other projects, such as `<repo>-admin`.

### Removing a Worker

- For dev and staging, remove its Access application first (below), then the Worker.
- Remove the Worker with `npx wrangler delete --name <worker>` (with `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` set) or from the dashboard.
- Renaming a repository or a component makes a new Worker and leaves the old one; remove the old one this way.

### The two owner-check refusals

- **`<component>: Worker <worker> was not deployed by the plane`.** The Worker exists, but none of the deployments Cloudflare lists carries a plane marker: it was made by hand or by another tool, or it was rolled back by hand more times than the deployments API lists (about ten).
  If nobody wants it, delete it and apply again. If it is wanted, rename the component so the plane uses a different Worker.
  If it is the plane's own Worker after many manual rollbacks, delete it and apply again: the apply recreates it from the commit's artefact.
- **`<component>: Worker <worker> belongs to <owner/repo>`.** Another project deployed that Worker name first, because repository and component names can meet through dashes (`shop` with `admin-site`, and `shop-admin` with `site`). The project asking renames its component.
- **The rare race.** Two colliding projects whose very first applies ran in the same minute could both deploy one Worker. The newest marker wins, so the Worker's owner is whichever deployed last. Spot it by two projects' markers in one Worker's deployments; delete the Worker and let the rightful project apply again, then have the other rename its component.

### Changes the plane does not see

A change made on the dashboard that does not create a deployment (for example a variable) is not seen by the plane, and stays until the Worker is next deployed or deleted.

### The fixture Workers

`cloudflare-fixture-web-prod` and `cloudflare-fixture-web-dev` belong to this repository's `acceptance` workflow, which recreates them; `cloudflare-plan-only-prod` and `cloudflare-fixture-web-staging` should never exist (they are only planned). They can be deleted at any time.

### Access

- A private Worker's application is the one named `<worker>` whose destination is that Worker (Zero Trust, Access, Applications). Delete it before or with the Worker: an application left for a deleted Worker protects nothing, and the next apply of a new Worker of that name makes a new one.
- **Two applications for one Worker**, or **two policies with one of the plane's names**, make the plane refuse, naming them. Delete the extra one (either is fine: they are the same) and apply again.
- The shared reusable policies `orc-plane-service-token` and `orc-plane-owner` are used by every private Worker. Delete them only when no application uses them; the next apply to dev or staging recreates them.
- The service token `orc-plane-tests` and the one-time PIN login method are the owner's (README, owner set-up steps 2 and 3); the plane never creates or deletes them. If either is missing or doubled, the plane refuses and names the step.
