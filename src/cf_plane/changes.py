"""Desired against observed, into parts and refusals; the apply order; the summary. Pure."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import ModuleType
from typing import Literal

from cf_plane import access, static_site
from cf_plane.contract import Component, Inputs, Refusal, ResultComponent, parse_inputs

# The kinds the plane offers. There is no plugin mechanism until a second kind exists.
KINDS: dict[str, ModuleType] = {static_site.KIND: static_site}
APPLICATION_WAIT_SECONDS = 30

Part = Literal["create", "update", "unchanged"]
Action = Literal["policy", "deploy", "app", "wait", "enable"]


@dataclass(frozen=True)
class Deployment:
    """One deployment the deployments API lists, with its message."""

    id: str
    created_on: str
    message: str | None


@dataclass(frozen=True)
class ObservedWorker:
    """What Cloudflare says about one Worker name."""

    exists: bool
    worker_id: str | None = None
    ids: frozenset[str] = frozenset()
    deployments: tuple[Deployment, ...] = ()
    workers_dev: bool = False
    previews: bool = False

    @property
    def newest_first(self) -> list[Deployment]:
        """The deployments, newest first; the first is the active one."""
        return sorted(self.deployments, key=lambda deployment: deployment.created_on, reverse=True)

    @property
    def owner(self) -> str | None:
        """The project in the newest deployment whose message is a plane marker."""
        for deployment in self.newest_first:
            marker = static_site.parse_marker(deployment.message)
            if marker is not None:
                return marker.project
        return None

    @property
    def active_message(self) -> str | None:
        """The message of the active deployment."""
        newest = self.newest_first
        return newest[0].message if newest else None


@dataclass(frozen=True)
class ObservedAccess:
    """The account's Access objects the plane reads."""

    policies: tuple[dict, ...]
    apps: tuple[dict, ...]
    service_tokens: tuple[dict, ...]
    identity_providers: tuple[dict, ...]


@dataclass(frozen=True)
class PolicyChange:
    """One shared policy: what to do to it, its id if it exists, and its desired body."""

    name: str
    part: Part
    policy_id: str | None
    body: dict = field(repr=False)


@dataclass(frozen=True)
class ComponentChange:
    """One component's Worker and, in dev and staging, its Access application."""

    component: Component
    worker: str
    url: str
    marker: str
    worker_part: Part
    deploy: bool
    enable: bool
    app_part: Part | None = None
    app_id: str | None = None
    worker_id: str | None = None
    worker_ids: frozenset[str] = frozenset()

    @property
    def unchanged(self) -> bool:
        """Whether nothing about this component needs to change."""
        return self.worker_part == "unchanged" and self.app_part in (None, "unchanged")


@dataclass(frozen=True)
class Plan:
    """Every change one plan or apply would make."""

    inputs: Inputs
    components: tuple[ComponentChange, ...]
    policies: tuple[PolicyChange, ...] = ()
    one_time_pin_id: str | None = None

    def component(self, name: str) -> ComponentChange:
        """The change for the component named NAME."""
        return next(change for change in self.components if change.component.name == name)

    def policy(self, name: str) -> PolicyChange:
        """The change for the shared policy named NAME."""
        return next(change for change in self.policies if change.name == name)


@dataclass(frozen=True)
class Step:
    """One outside effect of an apply, in order."""

    action: Action
    target: str = ""
    workers_dev: bool = True
    seconds: int = 0


def validate(
    *,
    project: str,
    commit: str,
    env: str,
    mode: str,
    components: str,
    plane_org: str | None,
    owner_email: str | None,
) -> Inputs:
    """Every input checked, including each component's Worker name, before any credential is read."""
    inputs = parse_inputs(
        project=project,
        commit=commit,
        env=env,
        mode=mode,
        components=components,
        plane_org=plane_org,
        owner_email=owner_email,
        kinds=KINDS.keys(),
    )
    problems = []
    for component in inputs.components:
        try:
            static_site.worker_name(inputs.repo, component.name, inputs.env)
        except Refusal as refusal:
            problems.append(str(refusal))
    if problems:
        raise Refusal("\n".join(problems))
    return inputs


def worker_names(inputs: Inputs) -> dict[str, str]:
    """Each component's Worker name, by component name."""
    return {
        component.name: static_site.worker_name(inputs.repo, component.name, inputs.env)
        for component in inputs.components
    }


def compare(
    inputs: Inputs, subdomain: str, workers: Mapping[str, ObservedWorker], observed_access: ObservedAccess | None
) -> Plan:
    """Desired against observed for every component and shared Access object; a refusal changes nothing."""
    names = worker_names(inputs)
    _check_owners(inputs, names, workers)
    changes = [
        _worker_change(inputs, component, names[component.name], subdomain, workers) for component in inputs.components
    ]
    if not inputs.private:
        return Plan(inputs, tuple(changes))
    if observed_access is None or inputs.owner_email is None:
        raise ValueError("a private plan needs the observed Access objects and the owner's email")
    return _with_access(Plan(inputs, tuple(changes)), observed_access, inputs.owner_email)


def _check_owners(inputs: Inputs, names: Mapping[str, str], workers: Mapping[str, ObservedWorker]) -> None:
    lines = []
    for component in inputs.components:
        worker = names[component.name]
        observed = workers[worker]
        if not observed.exists:
            continue
        owner = observed.owner
        if owner is None:
            lines.append(f"{component.name}: Worker {worker} was not deployed by the plane")
        elif owner != inputs.project:
            lines.append(f"{component.name}: Worker {worker} belongs to {owner}")
    if lines:
        raise Refusal(
            "\n".join(
                [
                    *lines,
                    "A Worker that belongs to another project stays with it: rename the component, "
                    "and a different component name gives a different Worker.",
                    "A Worker the plane did not deploy: see docs/cleanup.md (static-site) before deleting it.",
                ]
            )
        )


def _worker_change(
    inputs: Inputs, component: Component, worker: str, subdomain: str, workers: Mapping[str, ObservedWorker]
) -> ComponentChange:
    observed = workers[worker]
    desired = static_site.desired_marker(inputs.project, inputs.commit, worker)
    common = {
        "component": component,
        "worker": worker,
        "url": static_site.url(worker, subdomain),
        "marker": desired,
        "worker_id": observed.worker_id,
        "worker_ids": observed.ids,
    }
    if not observed.exists:
        # A new private Worker is deployed at no address, then reached through the script subdomain API.
        return ComponentChange(**common, worker_part="create", deploy=True, enable=inputs.private)
    if observed.active_message != desired:
        return ComponentChange(**common, worker_part="update", deploy=True, enable=False)
    settled = observed.workers_dev and not observed.previews
    return ComponentChange(**common, worker_part="unchanged" if settled else "update", deploy=False, enable=not settled)


def _with_access(plan: Plan, observed: ObservedAccess, owner_email: str) -> Plan:
    token_id = access.service_token_id(observed.service_tokens)
    pin_id = access.one_time_pin_id(observed.identity_providers)
    policies = tuple(
        _policy_change(observed.policies, desired) for desired in access.desired_policies(token_id, owner_email)
    )
    policy_ids = tuple(policy.policy_id for policy in policies)
    components = tuple(_app_change(change, observed.apps, policy_ids, pin_id) for change in plan.components)
    return Plan(plan.inputs, components, policies, pin_id)


def _policy_change(policies: Iterable[dict], desired: dict) -> PolicyChange:
    found = access.one_named(policies, desired["name"], "reusable Access policy")
    if found is None:
        return PolicyChange(desired["name"], "create", None, desired)
    part: Part = "unchanged" if access.policy_matches(found, desired) else "update"
    return PolicyChange(desired["name"], part, str(found["id"]), desired)


def _app_change(
    change: ComponentChange, apps: Iterable[dict], policy_ids: tuple[str | None, ...], pin_id: str
) -> ComponentChange:
    found = access.apps_for_worker(apps, change.worker_ids)
    if len(found) > 1:
        raise Refusal(
            f"{change.component.name}: the Worker {change.worker} has {len(found)} Access applications; "
            "the plane cannot tell which to keep, so delete the extra one and apply again "
            "(docs/cleanup.md, static-site, Access)."
        )
    if not found:
        return _replace(change, app_part="create")
    app = found[0]
    service_id, owner_id = policy_ids
    matches = (
        service_id is not None
        and owner_id is not None
        and change.worker_id is not None
        and access.app_matches(
            app,
            static_site.access_application(change.worker, change.worker_id, (service_id, owner_id), pin_id),
            change.worker_ids,
        )
    )
    return _replace(change, app_part="unchanged" if matches else "update", app_id=str(app["id"]))


def _replace(change: ComponentChange, **fields: object) -> ComponentChange:
    return ComponentChange(**{**change.__dict__, **fields})


def apply_steps(plan: Plan) -> tuple[Step, ...]:
    """The apply's outside effects, in an order that never makes a private Worker reachable before its application."""
    if not plan.inputs.private:
        return tuple(
            Step("deploy", change.component.name) if change.deploy else Step("enable", change.component.name)
            for change in plan.components
            if change.deploy or change.enable
        )
    steps = [Step("policy", policy.name) for policy in plan.policies if policy.part != "unchanged"]
    steps += [Step("deploy", c.component.name, workers_dev=False) for c in plan.components if c.worker_part == "create"]
    steps += [Step("app", c.component.name) for c in plan.components if c.app_part != "unchanged"]
    reachable = [Step("enable", c.component.name) for c in plan.components if c.enable]
    reachable += [Step("deploy", c.component.name) for c in plan.components if c.deploy and c.worker_part == "update"]
    if reachable and any(c.app_part == "create" for c in plan.components):
        steps.append(Step("wait", seconds=APPLICATION_WAIT_SECONDS))
    return (*steps, *reachable)


def header(inputs: Inputs) -> str:
    """The summary's first line: the env, mode, project and commit."""
    return f"{inputs.env} {inputs.mode} for {inputs.project} at {inputs.commit}"


def summary_lines(plan: Plan, *, applied: bool) -> list[str]:
    """One line per shared policy, then one per component, in the words of a plan or of a finished apply."""
    words = (
        {"create": "created", "update": "updated"} if applied else {"create": "would create", "update": "would update"}
    )
    lines = [f"Access policy {policy.name}: {words.get(policy.part, 'unchanged')}" for policy in plan.policies]
    for change in plan.components:
        parts = []
        if change.worker_part != "unchanged":
            parts.append(f"{words[change.worker_part]} Worker {change.worker}")
        if change.app_part is not None and change.app_part != "unchanged":
            parts.append(f"{words[change.app_part]} Access application {change.worker}")
        lines.append(f"{change.component.name}: {', '.join(parts) if parts else 'unchanged'}")
    return lines


def live_components(plan: Plan, steps: Iterable[Step], remaining_from: int) -> tuple[ResultComponent, ...]:
    """The components with no step left at or after REMAINING_FROM: those live at the new marker."""
    pending = list(steps)[remaining_from:]
    if any(step.action == "policy" for step in pending):
        unfinished = {change.component.name for change in plan.components if not change.unchanged}
    else:
        unfinished = {step.target for step in pending if step.action in ("deploy", "app", "enable")}
    return tuple(
        ResultComponent(name=change.component.name, url=change.url)
        for change in plan.components
        if change.component.name not in unfinished
    )


def all_components(plan: Plan) -> tuple[ResultComponent, ...]:
    """Every component with its address."""
    return tuple(ResultComponent(name=change.component.name, url=change.url) for change in plan.components)
