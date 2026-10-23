"""The Cloudflare API: subdomain, Worker, deployments, script subdomain and Access."""

from collections.abc import Iterable, Mapping

import httpx

from cf_plane.changes import Deployment, ObservedAccess, ObservedWorker
from cf_plane.contract import PlaneError

API = "https://api.cloudflare.com/client/v4"
TIMEOUT_SECONDS = 30.0
_PER_PAGE = 50
_MESSAGE = "workers/message"


class CloudflareError(PlaneError):
    """A Cloudflare API call failed. The message names the call and status, never the account or a token."""


class Cloudflare:
    """The calls the plane makes to one Cloudflare account, each with a timeout and no automatic retry."""

    def __init__(
        self,
        token: str,
        account_id: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = TIMEOUT_SECONDS,
    ) -> None:
        self._client = httpx.Client(
            base_url=f"{API}/accounts/{account_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
        )

    def _request(
        self, method: str, path: str, *, params: dict | None = None, body: dict | None = None, missing_ok: bool = False
    ) -> dict | None:
        try:
            response = self._client.request(method, path, params=params, json=body)
        except httpx.HTTPError as error:
            # The error's text holds the URL, which holds the account id: name only its type.
            raise CloudflareError(f"{method} {path} failed: {type(error).__name__}; run the workflow again.") from None
        if missing_ok and response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise CloudflareError(f"{method} {path} returned {response.status_code}{_errors(path, response)}")
        try:
            parsed = response.json()
        except ValueError:
            parsed = None
        if not isinstance(parsed, dict):
            raise CloudflareError(f"{method} {path} returned a body that is not a JSON object; run the workflow again.")
        return parsed

    def _object(self, method: str, path: str, *, body: dict | None = None, missing_ok: bool = False) -> dict:
        """The call's `result` when it is an object; empty when the thing is missing (404) and that is allowed."""
        response = self._request(method, path, body=body, missing_ok=missing_ok)
        result = (response or {}).get("result")
        return result if isinstance(result, dict) else {}

    def _items(self, path: str) -> list[dict]:
        """The call's `result` when it is a list of objects."""
        result = (self._request("GET", path) or {}).get("result")
        return [item for item in result if isinstance(item, dict)] if isinstance(result, list) else []

    def _all(self, path: str) -> tuple[dict, ...]:
        found: list[dict] = []
        page = 1
        while True:
            body = self._request("GET", path, params={"page": page, "per_page": _PER_PAGE}) or {}
            batch = body.get("result") or []
            found.extend(batch)
            total_pages = (body.get("result_info") or {}).get("total_pages")
            done = page >= total_pages if total_pages is not None else len(batch) < _PER_PAGE
            if not batch or done:
                return tuple(found)
            page += 1

    # --- Workers ----------------------------------------------------------------------------------------------

    def workers_subdomain(self) -> str:
        """The account's workers.dev subdomain."""
        subdomain = self._object("GET", "/workers/subdomain").get("subdomain")
        if not subdomain:
            raise CloudflareError(
                "the account has no workers.dev subdomain; the owner chooses one once (README, owner set-up step 1)."
            )
        return str(subdomain)

    def observe_workers(self, names: Iterable[str]) -> dict[str, ObservedWorker]:
        """What the account holds for each Worker name, with read-only calls."""
        tags = {str(script.get("id")): script.get("tag") for script in self._items("/workers/scripts")}
        return {name: self._observe_worker(name, tags) for name in names}

    def _observe_worker(self, name: str, tags: Mapping[str, object]) -> ObservedWorker:
        if name not in tags:
            return ObservedWorker(exists=False)
        tag = str(tags[name]) if tags[name] else None
        worker_id = self._workers_api_id(name) or tag
        subdomain = self._object("GET", f"/workers/scripts/{name}/subdomain")
        return ObservedWorker(
            exists=True,
            worker_id=worker_id,
            ids=frozenset(identifier for identifier in (worker_id, tag) if identifier),
            deployments=self._deployments(name),
            workers_dev=bool(subdomain.get("enabled")),
            previews=bool(subdomain.get("previews_enabled")),
        )

    def _workers_api_id(self, name: str) -> str | None:
        try:
            worker = self._object("GET", f"/workers/workers/{name}", missing_ok=True)
        except CloudflareError:
            return None
        return str(worker["id"]) if worker.get("id") else None

    def _deployments(self, name: str) -> tuple[Deployment, ...]:
        result = self._object("GET", f"/workers/scripts/{name}/deployments", missing_ok=True)
        versions: dict[str, str | None] = {}
        return tuple(
            Deployment(
                id=str(deployment.get("id")),
                created_on=str(deployment.get("created_on") or ""),
                message=self._message(name, deployment, versions),
            )
            for deployment in result.get("deployments") or []
        )

    def _message(self, name: str, deployment: dict, versions: dict[str, str | None]) -> str | None:
        """The deployment's message, or, when it has none, that of the one version it serves."""
        message = (deployment.get("annotations") or {}).get(_MESSAGE)
        if message:
            return str(message)
        served = deployment.get("versions") or []
        if len(served) != 1 or not served[0].get("version_id"):
            return None
        version_id = str(served[0]["version_id"])
        if version_id not in versions:
            version = self._object("GET", f"/workers/scripts/{name}/versions/{version_id}", missing_ok=True)
            versions[version_id] = (version.get("annotations") or {}).get(_MESSAGE)
        return versions[version_id]

    def worker_id(self, name: str) -> str | None:
        """The id an Access `worker` destination names, for a Worker that now exists."""
        observed = self.observe_workers([name])[name]
        return observed.worker_id

    def enable_workers_dev(self, name: str) -> None:
        """Turn the Worker's workers.dev address on, with previews off."""
        self._request("POST", f"/workers/scripts/{name}/subdomain", body={"enabled": True, "previews_enabled": False})

    # --- Access -----------------------------------------------------------------------------------------------

    def observe_access(self) -> ObservedAccess:
        """The reusable policies, applications, service tokens and login methods, with read-only calls."""
        return ObservedAccess(
            policies=self._all("/access/policies"),
            apps=self._all("/access/apps"),
            service_tokens=self._all("/access/service_tokens"),
            identity_providers=self._all("/access/identity_providers"),
        )

    def create_policy(self, body: dict) -> str:
        """Create a reusable policy and return its id."""
        return self._created("/access/policies", body)

    def update_policy(self, policy_id: str, body: dict) -> None:
        """Replace a reusable policy in place, keeping its id."""
        self._request("PUT", f"/access/policies/{policy_id}", body=body)

    def create_app(self, body: dict) -> str:
        """Create an Access application and return its id."""
        return self._created("/access/apps", body)

    def update_app(self, app_id: str, body: dict) -> None:
        """Replace an Access application in place, keeping its id."""
        self._request("PUT", f"/access/apps/{app_id}", body=body)

    def _created(self, path: str, body: dict) -> str:
        created = self._object("POST", path, body=body).get("id")
        if not created:
            raise CloudflareError(f"POST {path} returned no id; run the apply again.")
        return str(created)


def _errors(path: str, response: httpx.Response) -> str:
    """Cloudflare's error codes, and its messages except for Access, whose bodies stay out of the public log."""
    try:
        errors = response.json().get("errors") or []
    except ValueError:
        return ""
    if path.startswith("/access"):
        codes = [str(error.get("code")) for error in errors if isinstance(error, dict)]
        return f" (error codes {', '.join(codes)})" if codes else ""
    described = [
        f"{error.get('code')}: {str(error.get('message'))[:200]}" for error in errors if isinstance(error, dict)
    ]
    return f" ({'; '.join(described)})" if described else ""
