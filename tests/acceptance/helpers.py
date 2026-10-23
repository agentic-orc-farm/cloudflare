"""Helpers for the acceptance tests: running cf-plane, reading workflows and the README, and checking Cloudflare.

The live helpers write nothing secret to the test output: this repository's Actions logs are public, so failure
messages name Workers, addresses and counts, never tokens, the account id, the owner's email or Access bodies.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
FIXTURE_SITE = Path(__file__).resolve().parent / "fixture-site"
README = ROOT / "README.md"
CLEANUP = ROOT / "docs" / "cleanup.md"

ORG = "agentic-orc-farm"
EXAMPLE_PROJECT = f"{ORG}/example"
EXAMPLE_COMMIT = "4f2b9c0d1e3a5b7c9d0e2f4a6b8c0d2e4f6a8b0c"
NO_ARTEFACTS_COMMIT = "0" * 40

# The variables the criteria name as credentials, and a few more a tool might pick up on its own.
CREDENTIAL_VARIABLES = (
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_ACCOUNT_ID",
    "GITHUB_READ_TOKEN",
    "CF_ACCESS_CLIENT_ID",
    "CF_ACCESS_CLIENT_SECRET",
    "ACCESS_OWNER_EMAIL",
)
OTHER_CREDENTIALS = (
    "CLOUDFLARE_API_KEY",
    "CLOUDFLARE_EMAIL",
    "CF_API_TOKEN",
    "CF_ACCOUNT_ID",
    "GITHUB_TOKEN",
    "GH_TOKEN",
)
LIVE_VARIABLES = ("ACCEPTANCE_PROJECT", "ACCEPTANCE_COMMIT", *CREDENTIAL_VARIABLES)
LIVE_SKIP_REASON = "live: runs in the `acceptance` workflow, dispatched for a reviewed commit"

# Set in the environment of the nested `make acceptance` that AC12 runs, so it does not run itself again.
NESTED_MARKER = "CF_PLANE_ACCEPTANCE_NESTED"

SUMMARY_LIMIT = 1000


# --- Running cf-plane ---------------------------------------------------------------------------------------


def offline_environment(**extra: str) -> dict[str, str]:
    """The current environment without any credential or ACCEPTANCE_LIVE, with PLANE_ORG set."""
    removed = {*CREDENTIAL_VARIABLES, *OTHER_CREDENTIALS, "ACCEPTANCE_LIVE"}
    environment = {name: value for name, value in os.environ.items() if name not in removed}
    environment["PLANE_ORG"] = ORG
    environment.update(extra)
    return environment


def component(name: str, kind: str = "static-site", plane: str = "cloudflare", artefact: str = "site") -> dict:
    return {"name": name, "kind": kind, "plane": plane, "artefact": artefact}


@dataclass(frozen=True)
class Run:
    """One run of cf-plane, and the result.json it wrote, if any."""

    arguments: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    result: Any
    result_problem: str | None

    @property
    def summary(self) -> str:
        if isinstance(self.result, dict) and isinstance(self.result.get("summary"), str):
            return self.result["summary"]
        return ""

    @property
    def summary_lines(self) -> list[str]:
        return [line.strip() for line in self.summary.splitlines()]

    @property
    def components(self) -> list:
        if isinstance(self.result, dict) and isinstance(self.result.get("components"), list):
            return self.result["components"]
        return []

    def lists(self, name: str, url: str) -> bool:
        return any(
            isinstance(item, dict) and item.get("name") == name and item.get("url") == url for item in self.components
        )

    def describe(self) -> str:
        """What happened, for a failure message."""
        command = " ".join(self.arguments[:2])
        result = self.result_problem or json.dumps(self.result, indent=2)[:3000]
        return (
            f"cf-plane {command} exited {self.exit_code}\n"
            f"result.json: {result}\n"
            f"stdout (last 1500 characters): {self.stdout[-1500:]}\n"
            f"stderr (last 1500 characters): {self.stderr[-1500:]}"
        )


def run_cf_plane(
    arguments: list[str], environment: dict[str, str], result_path: Path | None = None, timeout: float = 120
) -> Run:
    """Run `uv run cf-plane ARGUMENTS` from the repository root and read the result.json it wrote."""
    if result_path is not None and result_path.exists():
        result_path.unlink()
    completed = subprocess.run(
        ["uv", "run", "cf-plane", *arguments],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    result: Any = None
    problem: str | None = None
    if result_path is not None:
        if not result_path.exists():
            problem = f"cf-plane did not write a result.json at --result {result_path}"
        else:
            try:
                result = json.loads(result_path.read_text())
            except json.JSONDecodeError as error:
                problem = f"result.json is not valid JSON: {error}"
    return Run(tuple(arguments), completed.returncode, completed.stdout, completed.stderr, result, problem)


def deploy_arguments(
    *, project: str, commit: str, env: str, mode: str, components: str | list, result_path: Path
) -> list[str]:
    components_text = components if isinstance(components, str) else json.dumps(components)
    return [
        "deploy",
        "--project",
        project,
        "--commit",
        commit,
        "--env",
        env,
        "--mode",
        mode,
        "--components",
        components_text,
        "--result",
        str(result_path),
    ]


def result_shape_problems(result: Any, *, components_empty: bool) -> list[str]:
    """Where a result.json differs from schema version 1; empty when it matches."""
    if not isinstance(result, dict):
        return [f"result.json is not a JSON object: {result!r}"]
    problems = []
    if set(result) != {"schema_version", "components", "summary"}:
        problems.append(f"keys are {sorted(result)}, not exactly schema_version, components and summary")
    version = result.get("schema_version")
    if isinstance(version, bool) or version != 1 or not isinstance(version, int):
        problems.append(f"schema_version is {version!r}, not the integer 1")
    problems.extend(_components_problems(result.get("components"), components_empty=components_empty))
    summary = result.get("summary")
    if not isinstance(summary, str):
        problems.append(f"summary is {summary!r}, not a string")
    elif len(summary) > SUMMARY_LIMIT:
        problems.append(f"summary is {len(summary)} characters, more than {SUMMARY_LIMIT}")
    return problems


def _components_problems(components: Any, *, components_empty: bool) -> list[str]:
    if not isinstance(components, list):
        return [f"components is {components!r}, not a list"]
    if components_empty and components:
        return [f"components is {components!r}, not empty"]
    problems = []
    for item in components:
        if not isinstance(item, dict) or set(item) != {"name", "url"}:
            problems.append(f"component {item!r} does not have exactly the keys name and url")
        elif not isinstance(item["name"], str) or not isinstance(item["url"], str):
            problems.append(f"component {item!r} has a name or url that is not a string")
    return problems


# --- Workflows and documents --------------------------------------------------------------------------------


def workflow_files() -> list[Path]:
    return sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])


def load_workflow(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict), f"{path.name} is not a YAML mapping"
    return data


def triggers(workflow: dict) -> dict:
    """The workflow's `on:` as a mapping of event to its settings. YAML 1.1 reads the key `on` as True."""
    on = workflow.get("on", workflow.get(True))
    if isinstance(on, str):
        return {on: None}
    if isinstance(on, list):
        return dict.fromkeys(on)
    if isinstance(on, dict):
        return on
    return {}


def steps(workflow: dict) -> list[tuple[str, dict]]:
    """Every step of every job, as (job name, step)."""
    found = []
    for job_name, job in (workflow.get("jobs") or {}).items():
        for step in (job or {}).get("steps") or []:
            found.append((job_name, step))
    return found


def expression_mentions(text: str, name: str) -> bool:
    """Whether a `${{ }}` expression in TEXT reads `inputs.NAME` (or `github.event.inputs.NAME`)."""
    for expression in re.findall(r"\$\{\{(.*?)\}\}", text, flags=re.DOTALL):
        if re.search(rf"(?<![\w.])(github\.event\.)?inputs\.{re.escape(name)}(?![\w-])", expression):
            return True
    return False


def markdown_section(text: str, heading: str) -> str | None:
    """The body under HEADING (for example `## Kinds`), up to the next heading of the same or a higher level."""
    level = len(heading) - len(heading.lstrip("#"))
    lines = text.splitlines()
    start = None
    in_fence = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if start is None:
            if line.strip() == heading:
                start = index + 1
            continue
        match = re.match(r"^(#+)\s", line)
        if match and len(match.group(1)) <= level:
            return "\n".join(lines[start:index])
    return None if start is None else "\n".join(lines[start:])


# --- Cloudflare, for the live criteria ----------------------------------------------------------------------


class CloudflareError(Exception):
    """A Cloudflare API call the tests needed did not succeed."""


class Cloudflare:
    """The few read and clean-up calls the live criteria need. Errors name the path, never a body or the account."""

    def __init__(self, token: str, account_id: str) -> None:
        self._client = httpx.Client(
            base_url=f"https://api.cloudflare.com/client/v4/accounts/{account_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )

    def _request(self, method: str, path: str, *, params: dict | None = None, missing_ok: bool = False) -> Any:
        response = self._client.request(method, path, params=params)
        if missing_ok and response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise CloudflareError(f"{method} {path} returned {response.status_code}")
        return response.json()

    def _all(self, path: str) -> list[dict]:
        found: list[dict] = []
        page = 1
        per_page = 50
        while True:
            body = self._request("GET", path, params={"page": page, "per_page": per_page})
            batch = body.get("result") or []
            found.extend(batch)
            info = body.get("result_info") or {}
            total_pages = info.get("total_pages")
            if not batch or (total_pages is not None and page >= total_pages):
                return found
            if total_pages is None and len(batch) < per_page:
                return found
            page += 1

    def workers_subdomain(self) -> str:
        return self._request("GET", "/workers/subdomain")["result"]["subdomain"]

    def script(self, name: str) -> dict | None:
        scripts = self._request("GET", "/workers/scripts")["result"] or []
        return next((script for script in scripts if script.get("id") == name), None)

    def worker_exists(self, name: str) -> bool:
        return self.script(name) is not None

    def worker_ids(self, name: str) -> set[str]:
        """Every id Cloudflare gives the Worker: the script's tag, and the Workers API id."""
        ids: set[str] = set()
        script = self.script(name)
        if script is None:
            return ids
        if script.get("tag"):
            ids.add(script["tag"])
        try:
            worker = self._request("GET", f"/workers/workers/{name}", missing_ok=True)
        except CloudflareError:
            worker = None
        if worker and isinstance(worker.get("result"), dict) and worker["result"].get("id"):
            ids.add(worker["result"]["id"])
        return ids

    def active_deployment_id(self, name: str) -> str | None:
        body = self._request("GET", f"/workers/scripts/{name}/deployments", missing_ok=True)
        if body is None:
            return None
        deployments = (body.get("result") or {}).get("deployments") or []
        if not deployments:
            return None
        newest = max(deployments, key=lambda deployment: deployment.get("created_on") or "")
        return newest.get("id")

    def script_subdomain(self, name: str) -> dict:
        return self._request("GET", f"/workers/scripts/{name}/subdomain")["result"]

    def access_apps(self) -> list[dict]:
        return self._all("/access/apps")

    def reusable_policies(self) -> list[dict]:
        return self._all("/access/policies")

    def service_tokens(self) -> list[dict]:
        return self._all("/access/service_tokens")

    def identity_providers(self) -> list[dict]:
        return self._all("/access/identity_providers")

    def apps_for_worker(self, worker: str, hostname: str) -> list[dict]:
        """Access applications for the Worker: by its `worker` destination, its hostname, or its name."""
        ids = self.worker_ids(worker)
        return [app for app in self.access_apps() if app_targets_worker(app, worker, hostname, ids)]

    def delete_app(self, app_id: str) -> None:
        self._request("DELETE", f"/access/apps/{app_id}", missing_ok=True)

    def delete_worker(self, name: str) -> None:
        self._request("DELETE", f"/workers/scripts/{name}", params={"force": "true"}, missing_ok=True)

    def remove_worker_and_apps(self, worker: str, hostname: str) -> None:
        """Remove the Worker's Access applications, then the Worker. Never the shared policies or the token."""
        for app in self.apps_for_worker(worker, hostname):
            self.delete_app(app["id"])
        if self.worker_exists(worker):
            self.delete_worker(worker)


def _host(address: str) -> str:
    return address.split("://", 1)[-1].split("/", 1)[0].lower()


def app_targets_worker(app: dict, worker: str, hostname: str, worker_ids: set[str]) -> bool:
    if app.get("name") == worker:
        return True
    for destination in app.get("destinations") or []:
        if destination.get("type") == "worker" and destination.get("worker_id") in worker_ids:
            return True
        if destination.get("uri") and _host(destination["uri"]) == hostname:
            return True
    domains = [app.get("domain") or "", *(app.get("self_hosted_domains") or [])]
    return any(domain and _host(domain) == hostname for domain in domains)


# --- The live context ---------------------------------------------------------------------------------------


@dataclass
class Live:
    """What the live criteria share: the project under test, its commit, credentials and a scratch folder."""

    project: str
    commit: str
    environment: dict[str, str]
    cloudflare: Cloudflare
    subdomain: str
    scratch: Path
    access_headers: dict[str, str] = field(repr=False)
    owner_email: str = field(repr=False)

    @property
    def owner(self) -> str:
        return self.project.split("/", 1)[0]

    @property
    def repo(self) -> str:
        return self.project.split("/", 1)[1]

    def hostname(self, worker: str) -> str:
        return f"{worker}.{self.subdomain}.workers.dev"

    def url(self, worker: str) -> str:
        return f"https://{self.hostname(worker)}"

    def deploy(
        self,
        label: str,
        *,
        env: str,
        mode: str,
        components: list,
        project: str | None = None,
        commit: str | None = None,
        without: tuple[str, ...] = (),
    ) -> Run:
        environment = {name: value for name, value in self.environment.items() if name not in without}
        result_path = self.scratch / f"{label}-result.json"
        arguments = deploy_arguments(
            project=project or self.project,
            commit=commit or self.commit,
            env=env,
            mode=mode,
            components=components,
            result_path=result_path,
        )
        return run_cf_plane(arguments, environment, result_path, timeout=900)


def get(url: str, headers: dict[str, str] | None = None) -> httpx.Response | None:
    """One GET that does not follow redirects; None when the request itself failed."""
    try:
        return httpx.get(url, headers=headers or {}, follow_redirects=False, timeout=15)
    except httpx.HTTPError:
        return None


def wait_for(url: str, check: Any, headers: dict[str, str] | None = None, seconds: float = 120) -> tuple[bool, str]:
    """GET URL every two seconds until CHECK(response) holds or SECONDS pass; returns (held, last seen)."""
    deadline = time.monotonic() + seconds
    last = "no response"
    while True:
        response = get(url, headers)
        if response is not None:
            if check(response):
                return True, f"{response.status_code}"
            last = f"status {response.status_code}, body starting {response.text[:120]!r}"
        if time.monotonic() >= deadline:
            return False, last
        time.sleep(2)


@dataclass
class Poller:
    """GETs a URL without the Access headers once a second, on its own thread, until stopped."""

    url: str
    observations: list[tuple[float, int | None]] = field(default_factory=list)
    _stop: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        with httpx.Client(follow_redirects=False, timeout=10) as client:
            while not self._stop.is_set():
                began = time.monotonic()
                try:
                    status: int | None = client.get(self.url).status_code
                except httpx.HTTPError:
                    status = None
                self.observations.append((began, status))
                self._stop.wait(max(0.0, 1.0 - (time.monotonic() - began)))

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=30)


@dataclass
class Step:
    """One live plan or apply, and what the tests observed around it, recorded before the next step changes it."""

    run: Run
    worker: str
    url: str
    deployment_before: str | None = None
    deployment_after: str | None = None
    worker_present_after: bool | None = None
    apps_after: int | None = None
    policies_after: dict[str, int] = field(default_factory=dict)
    apply_started: float | None = None
    apply_ended: float | None = None
    unauthorised_observations: list[tuple[float, int | None]] = field(default_factory=list)
    reached_with_headers: bool | None = None
    reached_detail: str = ""


def fixture_component(name: str = "fixture-web", artefact: str = "fixture-site") -> list[dict]:
    return [component(name, artefact=artefact)]


# --- The offline refusals (AC6 to AC9, AC23 to AC27), shared with AC10 ----------------------------------------

LONG_REPO = "a-rather-long-repository-name-for-the-plane"
LONG_COMPONENT = "marketing-site-component"
LONG_WORKER = f"{LONG_REPO}-{LONG_COMPONENT}-prod"


@dataclass(frozen=True)
class Refusal:
    """One `cf-plane deploy` the plane must refuse during validation, and what its summary must name."""

    case: str
    project: str = EXAMPLE_PROJECT
    commit: str = EXAMPLE_COMMIT
    env: str = "prod"
    mode: str = "plan"
    components: str | list = field(default_factory=lambda: [component("site")])
    must_name: tuple[str, ...] = ()


REFUSALS = (
    Refusal(
        "AC6-unknown-kind",
        components=[component("site", kind="edge-function")],
        must_name=("edge-function", "static-site"),
    ),
    Refusal("AC7-dev-without-owner-email", env="dev", must_name=("ACCESS_OWNER_EMAIL",)),
    Refusal("AC7-staging-without-owner-email", env="staging", must_name=("ACCESS_OWNER_EMAIL",)),
    Refusal("AC8-short-commit", commit="4f2b9c0", must_name=("commit",)),
    Refusal("AC8-uppercase-commit", commit=EXAMPLE_COMMIT.upper(), must_name=("commit",)),
    Refusal("AC8-non-hex-commit", commit="g" * 40, must_name=("commit",)),
    Refusal(
        "AC9-worker-name-too-long",
        project=f"{ORG}/{LONG_REPO}",
        components=[component(LONG_COMPONENT)],
        must_name=(LONG_WORKER, "63"),
    ),
    Refusal("AC23-project-of-another-organisation", project="someone-else/example", must_name=("project", ORG)),
    Refusal("AC24-repository-name-with-a-dot-and-capitals", project=f"{ORG}/My.Site", must_name=("project",)),
    Refusal("AC24-repository-name-with-an-underscore", project=f"{ORG}/my_site", must_name=("project",)),
    Refusal(
        "AC25-component-for-another-plane",
        components=[component("brochure", plane="aws")],
        must_name=("brochure", "plane"),
    ),
    Refusal(
        "AC26-repeated-component-name",
        components=[component("landing", artefact="landing-a"), component("landing", artefact="landing-b")],
        must_name=("landing",),
    ),
    Refusal("AC27-components-not-json", components="[{not json", must_name=("components",)),
    Refusal("AC27-components-empty-list", components="[]", must_name=("components",)),
    Refusal(
        "AC27-component-missing-a-key",
        components=[{"name": "site", "kind": "static-site", "plane": "cloudflare"}],
        must_name=("components",),
    ),
    Refusal(
        "AC27-component-with-an-extra-key",
        components=[{**component("site"), "region": "eu"}],
        must_name=("components",),
    ),
    # AC7's prod case: no Access check, but no credentials either, so it still fails, for another reason.
    Refusal("AC7-prod-without-credentials", env="prod"),
)
