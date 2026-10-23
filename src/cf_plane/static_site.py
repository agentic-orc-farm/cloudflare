"""The static-site kind: Worker name, address, wrangler configuration, marker and Access application. Pure."""

import hashlib
import json
import re
from pathlib import Path
from typing import NamedTuple

from cf_plane.contract import Refusal

KIND = "static-site"
# Changed deliberately, never automatically: a new date changes every Worker's marker, so the next apply of each
# component redeploys it.
COMPATIBILITY_DATE = "2026-10-01"
WORKER_NAME_LIMIT = 63

_MARKER = re.compile(r"orc project=(\S+/\S+) commit=([0-9a-f]{40}) config=([0-9a-f]{12})")
# Left out of the hash: the folder differs on every run, and the shim reads workers.dev and previews directly
# from the script subdomain API (a new private Worker is first deployed with workers.dev off).
_UNHASHED = ("workers_dev", "preview_urls")


class Marker(NamedTuple):
    """What a deployment message records: the owning project, the commit and the configuration's hash."""

    project: str
    commit: str
    config: str


def worker_name(repo: str, component: str, env: str) -> str:
    """The component's Worker: `<repo>-<component>-<env>`, refused rather than truncated when too long."""
    name = f"{repo}-{component}-{env}"
    if len(name) > WORKER_NAME_LIMIT:
        raise Refusal(
            f"components: {component} would be the Worker {name}, which is {len(name)} characters; "
            f"Worker names are at most {WORKER_NAME_LIMIT} characters, so use a shorter component name."
        )
    return name


def url(worker: str, subdomain: str) -> str:
    """The Worker's address on the account's workers.dev subdomain."""
    return f"https://{worker}.{subdomain}.workers.dev"


def wrangler_config(worker: str, assets: Path, *, workers_dev: bool = True) -> dict:
    """The wrangler configuration: the artefact served as it is, a real 404, and previews off."""
    return {
        "name": worker,
        "compatibility_date": COMPATIBILITY_DATE,
        "workers_dev": workers_dev,
        "preview_urls": False,
        "assets": {"directory": str(assets), "not_found_handling": "404-page"},
    }


def config_hash(config: dict) -> str:
    """The first 12 hex digits of the SHA-256 of the configuration without the assets path and the two flags."""
    hashed = {key: value for key, value in config.items() if key not in _UNHASHED}
    hashed["assets"] = {key: value for key, value in config["assets"].items() if key != "directory"}
    canonical = json.dumps(hashed, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def marker(project: str, commit: str, config: str) -> str:
    """The deployment message that records the owner, the commit and the configuration."""
    return f"orc project={project} commit={commit} config={config}"


def desired_marker(project: str, commit: str, worker: str) -> str:
    """The marker an up-to-date deployment of this Worker carries."""
    return marker(project, commit, config_hash(wrangler_config(worker, Path())))


def parse_marker(text: str | None) -> Marker | None:
    """The marker in a deployment message, or None when the message is not one."""
    if not text:
        return None
    match = _MARKER.fullmatch(text)
    return Marker(*match.groups()) if match else None


def access_application(worker: str, worker_id: str, policy_ids: tuple[str, str], one_time_pin_id: str) -> dict:
    """The private Worker's Access application: the two shared policies and only the one-time PIN login."""
    return {
        "type": "self_hosted",
        "name": worker,
        "destinations": [{"type": "worker", "worker_id": worker_id}],
        "policies": [{"id": policy_id, "precedence": index} for index, policy_id in enumerate(policy_ids, start=1)],
        "allowed_idps": [one_time_pin_id],
        "auto_redirect_to_identity": True,
        "app_launcher_visible": False,
    }
