"""AC11 to AC14 and AC34: the pinned wrangler, the offline suites, the README and the cleanup runbook. Offline."""

import json
import os
import re
import subprocess

import pytest
from tests.acceptance.helpers import (
    CLEANUP,
    CREDENTIAL_VARIABLES,
    NESTED_MARKER,
    README,
    ROOT,
    markdown_section,
)

# --- AC11 ---------------------------------------------------------------------------------------------------


def test_AC11_wrangler_is_pinned_to_one_exact_version_in_package_json_and_the_lock() -> None:
    package = json.loads((ROOT / "package.json").read_text())
    declared = {**package.get("devDependencies", {}), **package.get("dependencies", {})}.get("wrangler")
    assert isinstance(declared, str), "package.json does not depend on wrangler"
    assert re.fullmatch(r"\d+(\.\d+)*", declared), f"wrangler is {declared!r} in package.json, not an exact version"
    lock = json.loads((ROOT / "package-lock.json").read_text())
    locked = ((lock.get("packages") or {}).get("node_modules/wrangler") or {}).get("version")
    assert locked == declared, f"package-lock.json has wrangler {locked!r}, package.json {declared!r}"


# --- AC12 ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("target", ["test", "acceptance"])
def test_AC12_make_target_passes_without_credentials_or_acceptance_live(target: str) -> None:
    if os.environ.get(NESTED_MARKER):
        pytest.skip("inside the `make acceptance` that AC12 runs: it does not run itself again")
    removed = {*CREDENTIAL_VARIABLES, "ACCEPTANCE_LIVE"}
    environment = {name: value for name, value in os.environ.items() if name not in removed}
    environment[NESTED_MARKER] = "1"
    completed = subprocess.run(
        ["make", target], cwd=ROOT, env=environment, capture_output=True, text=True, timeout=1200, check=False
    )
    assert completed.returncode == 0, (
        f"make {target} exited {completed.returncode}\n"
        f"stdout (last 4000 characters):\n{completed.stdout[-4000:]}\n"
        f"stderr (last 2000 characters):\n{completed.stderr[-2000:]}"
    )


# --- AC13 ---------------------------------------------------------------------------------------------------


def _readme() -> str:
    return README.read_text()


def test_AC13_readme_kinds_section_lists_static_site() -> None:
    kinds = markdown_section(_readme(), "## Kinds")
    assert kinds is not None, "README.md has no `## Kinds` section"
    assert "static-site" in kinds


@pytest.mark.parametrize(
    "name",
    [
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_ACCOUNT_ID",
        "PLANE_READER_PRIVATE_KEY",
        "ACCESS_OWNER_EMAIL",
        "PLANE_READER_CLIENT_ID",
        "orc-plane-tests",
    ],
)
def test_AC13_readme_names_the_secrets_variable_and_service_token(name: str) -> None:
    assert re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", _readme()), f"README.md does not name {name}"


def test_AC13_readme_says_the_live_criteria_run_in_the_acceptance_workflow() -> None:
    readme = _readme()
    assert re.search(r"`acceptance`\s+workflow|acceptance\.yml", readme), "README.md does not name the workflow"
    lines = [line for line in readme.splitlines() if re.search(r"\blive\b", line, re.IGNORECASE)]
    assert any(re.search(r"`acceptance`|acceptance\.yml", line) for line in lines), (
        "no line of README.md names the `acceptance` workflow as where the live criteria run"
    )


# --- AC34 ---------------------------------------------------------------------------------------------------


def _private_environments() -> str:
    section = markdown_section(_readme(), "## Private environments")
    assert section is not None, "README.md has no `## Private environments` section"
    return section


@pytest.mark.parametrize(
    "name", ["CF_ACCESS_CLIENT_ID", "CF_ACCESS_CLIENT_SECRET", "CF-Access-Client-Id", "CF-Access-Client-Secret"]
)
def test_AC34_private_environments_names_the_secrets_and_headers(name: str) -> None:
    assert re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", _private_environments()), name


def test_AC34_private_environments_says_prod_is_public_and_dev_and_staging_are_not() -> None:
    sentences = re.split(r"(?<=[.;:])\s+|\n", _private_environments())
    prod_public = any(
        re.search(r"\bprod\b", sentence) and re.search(r"\bpublic\b", sentence, re.IGNORECASE) for sentence in sentences
    )
    assert prod_public, "no sentence says that prod is public"
    private = any(
        re.search(r"\bdev\b", sentence)
        and re.search(r"\bstaging\b", sentence)
        and re.search(r"\bAccess\b|\bprivate\b|\bnot public\b", sentence)
        for sentence in sentences
    )
    assert private, "no sentence says that dev and staging are behind Access (not public)"


# --- AC14 ---------------------------------------------------------------------------------------------------


def test_AC14_cleanup_runbook_has_a_static_site_section_with_an_access_subsection() -> None:
    assert CLEANUP.is_file(), "docs/cleanup.md does not exist"
    static_site = markdown_section(CLEANUP.read_text(), "## static-site")
    assert static_site is not None, "docs/cleanup.md has no `## static-site` section"
    assert markdown_section(static_site, "### Access") is not None, "`## static-site` has no `### Access` section"
