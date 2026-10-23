"""Inputs, components and result.json as frozen pydantic models. Pure."""

import json
import re
from collections import Counter
from collections.abc import Collection
from typing import Literal

from pydantic import BaseModel, ConfigDict

PLANE = "cloudflare"
ENVS = ("dev", "staging", "prod")
PRIVATE_ENVS = ("dev", "staging")
MODES = ("plan", "apply")
COMPONENT_KEYS = frozenset({"name", "kind", "plane", "artefact"})
SUMMARY_LIMIT = 1000

_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
_REPO = re.compile(r"[a-z0-9-]+")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+")
_QUOTE_LIMIT = 64


class PlaneError(Exception):
    """An expected failure: the message says what is wrong and what to do, and is safe to paste into a prompt."""


class Refusal(PlaneError):
    """The plane refused before changing anything."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Component(_Frozen):
    """One deploy.yaml entry for this plane."""

    name: str
    kind: str
    plane: str
    artefact: str


class Inputs(_Frozen):
    """The validated inputs of one plan or apply."""

    project: str
    commit: str
    env: Literal["dev", "staging", "prod"]
    mode: Literal["plan", "apply"]
    components: tuple[Component, ...]
    owner_email: str | None = None

    @property
    def owner(self) -> str:
        """The organisation that owns the project."""
        return self.project.split("/", 1)[0]

    @property
    def repo(self) -> str:
        """The project's repository name, without its owner."""
        return self.project.split("/", 1)[1]

    @property
    def private(self) -> bool:
        """Whether this environment sits behind Cloudflare Access."""
        return self.env in PRIVATE_ENVS


class ResultComponent(_Frozen):
    """One component's name and address in result.json."""

    name: str
    url: str


class Result(_Frozen):
    """result.json, schema version 1: the contract with the driver."""

    schema_version: Literal[1] = 1
    components: tuple[ResultComponent, ...]
    summary: str

    def to_json(self) -> str:
        """The JSON written to result.json, with the summary fitted to its limit."""
        data = self.model_dump(mode="json")
        data["summary"] = fit_summary(self.summary)
        return json.dumps(data, indent=2) + "\n"


def quote(value: object) -> str:
    """Untrusted text for a message: JSON-escaped and shortened, so it is safe to paste into a prompt."""
    text = str(value)
    if len(text) > _QUOTE_LIMIT:
        text = text[:_QUOTE_LIMIT] + "..."
    return json.dumps(text)


def fit_summary(summary: str, limit: int = SUMMARY_LIMIT) -> str:
    """The summary within LIMIT characters: the first line, as many whole lines as fit, then how many were left."""
    if len(summary) <= limit:
        return summary
    lines = summary.splitlines()
    kept = [lines[0][: limit - 60]]
    for index, line in enumerate(lines[1:], start=1):
        tail = f"({len(lines) - index} more lines: see the run log)"
        if len("\n".join([*kept, line, tail])) > limit:
            return "\n".join([*kept, tail])
        kept.append(line)
    return "\n".join(kept)


def parse_inputs(
    *,
    project: str,
    commit: str,
    env: str,
    mode: str,
    components: str,
    plane_org: str | None,
    owner_email: str | None,
    kinds: Collection[str],
) -> Inputs:
    """Check every input and return them typed, or raise a Refusal naming every problem found."""
    problems = [
        *_project_problems(project, plane_org),
        *_commit_problems(commit),
        *_choice_problems("env", env, ENVS),
        *_choice_problems("mode", mode, MODES),
        *_owner_email_problems(env, owner_email),
    ]
    parsed, component_problems = _parse_components(components, kinds)
    problems.extend(component_problems)
    if problems:
        raise Refusal("\n".join(problems))
    return Inputs.model_validate(
        {
            "project": project,
            "commit": commit,
            "env": env,
            "mode": mode,
            "components": parsed,
            "owner_email": owner_email if env in PRIVATE_ENVS else None,
        }
    )


def parse_component_config(project: str, env: str, component: str, kinds: Collection[str]) -> tuple[str, Component]:
    """The repository name and the one component `wrangler-config` translates, or a Refusal; reads no environment."""
    owner = project.partition("/")[0]
    problems = [*_project_problems(project, owner or "<owner>"), *_choice_problems("env", env, ENVS)]
    try:
        item = json.loads(component)
    except json.JSONDecodeError:
        item = None
    parsed: Component | None = None
    if isinstance(item, dict):
        parsed, component_problems = _parse_component(1, item, kinds)
        problems.extend(component_problems)
    else:
        problems.append("components: --component must be one JSON object with the keys artefact, kind, name and plane.")
    if problems or parsed is None:
        raise Refusal("\n".join(problems))
    return project.partition("/")[2], parsed


def _project_problems(project: str, plane_org: str | None) -> list[str]:
    if not plane_org:
        return [
            "PLANE_ORG: not set; the workflow sets it to the repository's owner, the organisation the plane serves."
        ]
    owner, slash, repo = project.partition("/")
    if not slash or not repo or "/" in repo or owner != plane_org:
        return [
            f"project: {quote(project)} is not <owner>/<repo> with the owner {plane_org}; "
            f"the plane deploys only repositories of the organisation {plane_org}."
        ]
    if not _REPO.fullmatch(repo):
        return [
            f"project: the repository name {quote(repo)} may contain only lowercase letters, digits and dashes; "
            "the plane refuses rather than rewrites it, so rename the repository."
        ]
    return []


def _commit_problems(commit: str) -> list[str]:
    if _COMMIT.fullmatch(commit):
        return []
    return [f"commit: {quote(commit)} is not 40 lowercase hexadecimal characters; pass the commit's full sha."]


def _choice_problems(name: str, value: str, choices: tuple[str, ...]) -> list[str]:
    if value in choices:
        return []
    return [f"{name}: {quote(value)} is not one of {', '.join(choices)}."]


def _owner_email_problems(env: str, owner_email: str | None) -> list[str]:
    if env not in PRIVATE_ENVS:
        return []
    if not owner_email:
        return [
            f"ACCESS_OWNER_EMAIL: not set; {env} sits behind Cloudflare Access and lets the owner in by email, "
            "so set the repository secret ACCESS_OWNER_EMAIL (README, owner set-up step 5)."
        ]
    if not _EMAIL.fullmatch(owner_email):
        return [
            "ACCESS_OWNER_EMAIL: does not look like an email (one @, no spaces); "
            "fix the repository secret ACCESS_OWNER_EMAIL (README, owner set-up step 5)."
        ]
    return []


def _parse_components(text: str, kinds: Collection[str]) -> tuple[list[Component], list[str]]:
    try:
        items = json.loads(text)
    except json.JSONDecodeError as error:
        return [], [f"components: not valid JSON ({error.msg} at character {error.pos}); pass a JSON list."]
    if not isinstance(items, list) or not items:
        return [], ["components: must be a non-empty JSON list of the project's deploy.yaml entries for this plane."]
    parsed: list[Component] = []
    problems: list[str] = []
    for position, item in enumerate(items, start=1):
        component, item_problems = _parse_component(position, item, kinds)
        problems.extend(item_problems)
        if component is not None:
            parsed.append(component)
    for name, count in Counter(component.name for component in parsed).items():
        if count > 1:
            problems.append(
                f"components: the name {quote(name)} appears {count} times; component names must be unique."
            )
    return parsed, problems


def _parse_component(position: int, item: object, kinds: Collection[str]) -> tuple[Component | None, list[str]]:
    if not isinstance(item, dict) or set(item) != COMPONENT_KEYS:
        keys = sorted(item) if isinstance(item, dict) else type(item).__name__
        return None, [
            f"components: item {position} must have exactly the keys artefact, kind, name and plane; "
            f"it has {quote(keys)}."
        ]
    bad = [key for key in sorted(COMPONENT_KEYS) if not isinstance(item[key], str) or not _NAME.fullmatch(item[key])]
    if bad:
        return None, [
            f"components: item {position} has {', '.join(bad)} not matching [a-z0-9][a-z0-9-]{{0,62}}; "
            "use lowercase letters, digits and dashes, starting with a letter or digit."
        ]
    component = Component.model_validate(item)
    problems = []
    if component.plane != PLANE:
        problems.append(
            f"components: {quote(component.name)} has plane {quote(component.plane)}; "
            f"this plane deploys only components whose plane is {PLANE}."
        )
    if component.kind not in kinds:
        problems.append(
            f"components: {quote(component.name)} has kind {quote(component.kind)}, which this plane does not offer; "
            f"the kinds offered are: {', '.join(sorted(kinds))}."
        )
    return component, problems
