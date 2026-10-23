"""Shared test helpers; conftest.py holds fixtures only and tests never import from each other.

FakeCloudflare and FakeGitHub are httpx.MockTransport handlers that keep state, so tests assert on what the
account holds afterwards rather than on which calls were made. The fake wrangler is a real executable that
records each deploy in a log file; FakeCloudflare reads that log on every request, as if wrangler had called it.
"""

from __future__ import annotations

import io
import itertools
import json
import os
import stat
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

ACCOUNT = "acc0123456789abcdef"
TOKEN = "cf-test-token"
READ_TOKEN = "gh-read-token"
ORG = "agentic-orc-farm"
PROJECT = f"{ORG}/example"
COMMIT = "4f2b9c0d1e3a5b7c9d0e2f4a6b8c0d2e4f6a8b0c"
OWNER_EMAIL = "owner@example.com"
API_PREFIX = f"/client/v4/accounts/{ACCOUNT}"

FAKE_WRANGLER = '''#!{python}
"""A scripted stand-in for wrangler: records each deploy, and fails when told to."""
import json, os, sys
arguments = sys.argv[1:]
config_path = arguments[arguments.index("--config") + 1]
message = arguments[arguments.index("--message") + 1]
config = json.loads(open(config_path, encoding="utf-8").read())
directory = config["assets"]["directory"]
files = sorted(
    os.path.relpath(os.path.join(root, name), directory)
    for root, _, names in os.walk(directory) for name in names
)
contents = {{name: open(os.path.join(directory, name), encoding="utf-8").read() for name in files}}
record = {{"arguments": arguments, "config": config, "message": message, "files": contents,
          "token": os.environ.get("CLOUDFLARE_API_TOKEN"), "account": os.environ.get("CLOUDFLARE_ACCOUNT_ID"),
          "metrics": os.environ.get("WRANGLER_SEND_METRICS"),
          "leaked": [n for n in ("GITHUB_READ_TOKEN", "ACCESS_OWNER_EMAIL") if n in os.environ]}}
print("Uploaded " + config["name"] + " to account " + str(os.environ.get("CLOUDFLARE_ACCOUNT_ID")))
exit_code = int(os.environ.get("FAKE_WRANGLER_EXIT", "0"))
if exit_code == 0:
    with open(os.environ["FAKE_WRANGLER_LOG"], "a", encoding="utf-8") as log:
        log.write(json.dumps(record) + "\\n")
else:
    print("deploy failed", file=sys.stderr)
sys.exit(exit_code)
'''


def write_fake_wrangler(folder: Path) -> Path:
    """Write the fake wrangler executable into FOLDER and return its path."""
    path = folder / "wrangler"
    path.write_text(FAKE_WRANGLER.format(python=sys.executable), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def read_wrangler_log(path: Path) -> list[dict]:
    """Every deploy the fake wrangler recorded."""
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


@dataclass
class FakeScript:
    """One Worker in the fake account."""

    name: str
    tag: str
    worker_id: str
    deployments: list[dict] = field(default_factory=list)
    versions: dict[str, dict] = field(default_factory=dict)
    workers_dev: bool = False
    previews: bool = True
    files: dict[str, str] = field(default_factory=dict)


@dataclass
class FakeCloudflare:
    """A Cloudflare account behind httpx.MockTransport: Workers, deployments, subdomains and Access."""

    wrangler_log: Path | None = None
    subdomain: str = "acme"
    known_scripts: dict[str, FakeScript] = field(default_factory=dict)
    policies: list[dict] = field(default_factory=list)
    apps: list[dict] = field(default_factory=list)
    service_tokens: list[dict] = field(default_factory=lambda: [{"id": "tok-1", "name": "orc-plane-tests"}])
    identity_providers: list[dict] = field(
        default_factory=lambda: [{"id": "gh-1", "type": "github"}, {"id": "pin-1", "type": "onetimepin"}]
    )
    deployment_annotations: bool = True
    workers_api: bool = True
    page_size: int = 2
    fail: dict[tuple[str, str], int] = field(default_factory=dict)
    recorded_effects: list[str] = field(default_factory=list)
    requests: list[tuple[str, str]] = field(default_factory=list)
    _ingested: int = 0
    _clock: itertools.count = field(default_factory=lambda: itertools.count(1))
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    @property
    def scripts(self) -> dict[str, FakeScript]:
        """The Workers, including what the fake wrangler deployed since the last request."""
        self._ingest()
        return self.known_scripts

    @property
    def effects(self) -> list[str]:
        """Every change made to the account, in order, including the fake wrangler's deploys."""
        self._ingest()
        return self.recorded_effects

    # --- setting up state -------------------------------------------------------------------------------------

    def add_script(self, name: str, message: str | None, *, workers_dev: bool = True, previews: bool = False) -> None:
        script = self.scripts.setdefault(name, FakeScript(name, f"tag-{name}", f"wid-{name}"))
        self._deploy(script, message)
        script.workers_dev, script.previews = workers_dev, previews

    def _deploy(self, script: FakeScript, message: str | None) -> None:
        tick = next(self._clock)
        version_id = f"v{tick}"
        script.versions[version_id] = {"id": version_id, "annotations": {"workers/message": message} if message else {}}
        annotations = {"workers/message": message} if message and self.deployment_annotations else {}
        script.deployments.append(
            {
                "id": f"dep-{script.name}-{tick}",
                "created_on": f"2026-10-23T00:{tick // 60:02d}:{tick % 60:02d}.000000Z",
                "source": "wrangler",
                "strategy": "percentage",
                "annotations": annotations,
                "versions": [{"version_id": version_id, "percentage": 100}],
            }
        )

    def active_deployment(self, name: str) -> str | None:
        script = self.scripts.get(name)
        return script.deployments[-1]["id"] if script and script.deployments else None

    def apps_for(self, name: str) -> list[dict]:
        script = self.scripts.get(name)
        if script is None:
            return []
        return [
            app
            for app in self.apps
            if any(d.get("worker_id") in (script.worker_id, script.tag) for d in app.get("destinations") or [])
        ]

    def policy_named(self, name: str) -> list[dict]:
        return [policy for policy in self.policies if policy["name"] == name]

    # --- the API ----------------------------------------------------------------------------------------------

    def handle(self, request: httpx.Request) -> httpx.Response:
        self._ingest()
        assert request.headers.get("authorization") == f"Bearer {TOKEN}", "every request carries the API token"
        assert request.url.host == "api.cloudflare.com"
        assert request.url.path.startswith(API_PREFIX), request.url.path
        path = request.url.path[len(API_PREFIX) :]
        self.requests.append((request.method, path))
        for (method, prefix), status in self.fail.items():
            if request.method == method and path.startswith(prefix):
                return _error(status, "injected failure")
        body = json.loads(request.content) if request.content else None
        query = {key: values[0] for key, values in parse_qs(urlparse(str(request.url)).query).items()}
        return self._route(request.method, path.strip("/").split("/"), body, query)

    def _route(self, method: str, parts: list[str], body: Any, query: dict) -> httpx.Response:  # noqa: C901, PLR0911, PLR0912
        match method, parts:
            case "GET", ["workers", "subdomain"]:
                return _ok({"subdomain": self.subdomain})
            case "GET", ["workers", "scripts"]:
                return _ok([{"id": s.name, "tag": s.tag} for s in self.scripts.values()])
            case "GET", ["workers", "workers", name]:
                script = self.scripts.get(name)
                if not self.workers_api:
                    return _error(400, "not available")
                return _ok({"id": script.worker_id, "name": name}) if script else _error(404, "not found")
            case "GET", ["workers", "scripts", name, "deployments"]:
                script = self.scripts.get(name)
                return _ok({"deployments": list(reversed(script.deployments))}) if script else _error(404, "no script")
            case "GET", ["workers", "scripts", name, "versions", version]:
                return _ok(self.scripts[name].versions[version])
            case "GET", ["workers", "scripts", name, "subdomain"]:
                script = self.scripts[name]
                return _ok({"enabled": script.workers_dev, "previews_enabled": script.previews})
            case "POST", ["workers", "scripts", name, "subdomain"]:
                script = self.scripts[name]
                script.workers_dev, script.previews = body["enabled"], body["previews_enabled"]
                self.effects.append(f"enable {name}")
                return _ok({"enabled": script.workers_dev, "previews_enabled": script.previews})
            case "GET", ["access", collection]:
                return self._page(getattr(self, _COLLECTIONS[collection]), query)
            case "POST", ["access", ("apps" | "policies") as collection]:
                item = {**body, "id": f"{collection}-{next(self._ids)}"}
                if collection == "apps":
                    item["policies"] = self._expand(body["policies"])
                getattr(self, collection).append(item)
                self.effects.append(f"create {collection} {body['name']}")
                return _ok(item)
            case "PUT", ["access", ("apps" | "policies") as collection, item_id]:
                items = getattr(self, collection)
                index = next(i for i, item in enumerate(items) if item["id"] == item_id)
                items[index] = {**body, "id": item_id}
                if collection == "apps":
                    items[index]["policies"] = self._expand(body["policies"])
                self.effects.append(f"update {collection} {body['name']}")
                return _ok(items[index])
        return _error(404, f"no route for {method} {'/'.join(parts)}")

    def _expand(self, references: list[dict]) -> list[dict]:
        by_id = {policy["id"]: policy for policy in self.policies}
        return [{**by_id.get(ref["id"], {}), "id": ref["id"], "precedence": ref["precedence"]} for ref in references]

    def _page(self, items: list[dict], query: dict) -> httpx.Response:
        page = int(query.get("page", 1))
        per_page = min(int(query.get("per_page", 20)), self.page_size)
        chunk = items[(page - 1) * per_page : page * per_page]
        total_pages = max(1, -(-len(items) // per_page))
        info = {"page": page, "per_page": per_page, "total_pages": total_pages, "total_count": len(items)}
        return httpx.Response(200, json={"success": True, "errors": [], "result": chunk, "result_info": info})

    def _ingest(self) -> None:
        if self.wrangler_log is None:
            return
        records = read_wrangler_log(self.wrangler_log)
        for record in records[self._ingested :]:
            config = record["config"]
            name = config["name"]
            script = self.known_scripts.setdefault(name, FakeScript(name, f"tag-{name}", f"wid-{name}"))
            self._deploy(script, record["message"])
            script.workers_dev, script.previews = config["workers_dev"], config["preview_urls"]
            script.files = record["files"]
            self.recorded_effects.append(f"deploy {name} workers_dev={config['workers_dev']}")
        self._ingested = len(records)


_COLLECTIONS = {
    "apps": "apps",
    "policies": "policies",
    "service_tokens": "service_tokens",
    "identity_providers": "identity_providers",
}


def _ok(result: Any) -> httpx.Response:
    return httpx.Response(200, json={"success": True, "errors": [], "messages": [], "result": result})


def _error(status: int, message: str) -> httpx.Response:
    return httpx.Response(status, json={"success": False, "errors": [{"code": 10000 + status, "message": message}]})


# --- GitHub -----------------------------------------------------------------------------------------------------


def zip_bytes(files: dict[str, str | bytes], *, symlinks: dict[str, str] | None = None) -> bytes:
    """A zip holding FILES, and SYMLINKS as symbolic links (name to target)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
        for name, target in (symlinks or {}).items():
            info = zipfile.ZipInfo(name)
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, target)
    return buffer.getvalue()


@dataclass
class FakeGitHub:
    """The Actions artefacts API and its storage redirect, behind httpx.MockTransport."""

    artefacts: list[dict] = field(default_factory=list)
    zips: dict[int, bytes] = field(default_factory=dict)
    page_size: int = 2
    requests: list[str] = field(default_factory=list)
    storage_headers: list[dict] = field(default_factory=list)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(100))

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def add(
        self,
        name: str,
        files: dict[str, str | bytes],
        *,
        commit: str = COMMIT,
        created_at: str = "2026-10-23T10:00:00Z",
        expired: bool = False,
        fork: bool = False,
        project: str = PROJECT,
        content: bytes | None = None,
    ) -> int:
        artefact_id = next(self._ids)
        self.artefacts.append(
            {
                "id": artefact_id,
                "name": name,
                "project": project,
                "size_in_bytes": 1000,
                "expired": expired,
                "created_at": created_at,
                "workflow_run": {
                    "id": artefact_id * 10,
                    "repository_id": 1,
                    "head_repository_id": 2 if fork else 1,
                    "head_sha": commit,
                },
            }
        )
        self.zips[artefact_id] = content if content is not None else zip_bytes(files)
        return artefact_id

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(f"{request.url.host}{request.url.path}")
        if request.url.host == "storage.example.net":
            self.storage_headers.append(dict(request.headers))
            artefact_id = int(request.url.path.rsplit("/", 1)[-1])
            return httpx.Response(200, content=self.zips[artefact_id])
        assert request.url.host == "api.github.com"
        assert request.headers.get("authorization") == f"Bearer {READ_TOKEN}"
        parts = request.url.path.strip("/").split("/")
        project = f"{parts[1]}/{parts[2]}"
        if parts[-1] == "zip":
            location = f"https://storage.example.net/blobs/{parts[-2]}"
            return httpx.Response(302, headers={"location": location})
        query = {key: values[0] for key, values in parse_qs(urlparse(str(request.url)).query).items()}
        matching = [
            {key: value for key, value in artefact.items() if key != "project"}
            for artefact in self.artefacts
            if artefact["project"] == project and artefact["name"] == query.get("name")
        ]
        page = int(query.get("page", 1))
        per_page = min(int(query.get("per_page", 30)), self.page_size)
        chunk = matching[(page - 1) * per_page : page * per_page]
        return httpx.Response(200, json={"total_count": len(matching), "artifacts": chunk})


def environment_without_credentials() -> dict[str, str]:
    """The current environment without anything a test could mistake for a real credential."""
    removed = {
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_ACCOUNT_ID",
        "GITHUB_READ_TOKEN",
        "ACCESS_OWNER_EMAIL",
        "CF_ACCESS_CLIENT_ID",
        "CF_ACCESS_CLIENT_SECRET",
    }
    return {name: value for name, value in os.environ.items() if name not in removed}
