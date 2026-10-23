import json

import pytest

from cf_plane import changes, static_site
from cf_plane.changes import Deployment, ObservedAccess, ObservedWorker, Step
from cf_plane.contract import Refusal

ORG = "agentic-orc-farm"
PROJECT = f"{ORG}/example"
COMMIT = "4f2b9c0d1e3a5b7c9d0e2f4a6b8c0d2e4f6a8b0c"
OLD_COMMIT = "1" * 40
EMAIL = "owner@example.com"
TOKEN = {"id": "tok-1", "name": "orc-plane-tests"}
PIN = {"id": "pin-1", "type": "onetimepin"}


def component(name: str = "site") -> dict:
    return {"name": name, "kind": "static-site", "plane": "cloudflare", "artefact": "site"}


def inputs(env: str = "prod", mode: str = "plan", names: tuple[str, ...] = ("site",), project: str = PROJECT):
    return changes.validate(
        project=project,
        commit=COMMIT,
        env=env,
        mode=mode,
        components=json.dumps([component(name) for name in names]),
        plane_org=ORG,
        owner_email=EMAIL,
    )


def marker_for(worker: str, project: str = PROJECT, commit: str = COMMIT) -> str:
    return static_site.desired_marker(project, commit, worker)


def deployed(worker: str, *messages: str | None, workers_dev: bool = True, previews: bool = False) -> ObservedWorker:
    """A Worker whose deployments carry MESSAGES, oldest first."""
    deployments = tuple(
        Deployment(f"d{index}", f"2026-10-{10 + index:02d}T00:00:00Z", message)
        for index, message in enumerate(messages)
    )
    return ObservedWorker(
        exists=True,
        worker_id=f"id-{worker}",
        ids=frozenset({f"id-{worker}", f"tag-{worker}"}),
        deployments=deployments,
        workers_dev=workers_dev,
        previews=previews,
    )


ABSENT = ObservedWorker(exists=False)


def policies(token_id: str = "tok-1", email: str = EMAIL) -> tuple[dict, ...]:
    service, owner = changes.access.desired_policies(token_id, email)
    return ({**service, "id": "pol-svc"}, {**owner, "id": "pol-own"})


def app_for(worker: str, **change: object) -> dict:
    body = static_site.access_application(worker, f"id-{worker}", ("pol-svc", "pol-own"), "pin-1")
    return {"id": f"app-{worker}", **body, **change}


def observed_access(apps: tuple[dict, ...] = (), existing_policies: tuple[dict, ...] | None = None) -> ObservedAccess:
    return ObservedAccess(
        policies=policies() if existing_policies is None else existing_policies,
        apps=apps,
        service_tokens=(TOKEN,),
        identity_providers=(PIN,),
    )


# --- validate -------------------------------------------------------------------------------------------------


def test_validate_refuses_a_worker_name_over_63_characters() -> None:
    long_repo = "a-rather-long-repository-name-for-the-plane"
    with pytest.raises(Refusal) as caught:
        changes.validate(
            project=f"{ORG}/{long_repo}",
            commit=COMMIT,
            env="prod",
            mode="plan",
            components=json.dumps([component("marketing-site-component")]),
            plane_org=ORG,
            owner_email=None,
        )
    assert f"{long_repo}-marketing-site-component-prod" in str(caught.value)
    assert "63" in str(caught.value)


def test_validate_offers_static_site() -> None:
    assert list(changes.KINDS) == ["static-site"]


# --- prod -----------------------------------------------------------------------------------------------------


def test_a_missing_prod_worker_is_created_by_one_deploy() -> None:
    plan = changes.compare(inputs(), "acme", {"example-site-prod": ABSENT}, None)
    change = plan.component("site")
    assert (change.worker_part, change.deploy, change.enable, change.app_part) == ("create", True, False, None)
    assert change.url == "https://example-site-prod.acme.workers.dev"
    assert changes.apply_steps(plan) == (Step("deploy", "site"),)
    assert changes.summary_lines(plan, applied=False) == ["site: would create Worker example-site-prod"]
    assert changes.summary_lines(plan, applied=True) == ["site: created Worker example-site-prod"]


def test_an_owned_worker_with_the_desired_marker_is_unchanged() -> None:
    worker = "example-site-prod"
    plan = changes.compare(inputs(), "acme", {worker: deployed(worker, marker_for(worker))}, None)
    assert plan.component("site").worker_part == "unchanged"
    assert changes.apply_steps(plan) == ()
    assert changes.summary_lines(plan, applied=True) == ["site: unchanged"]


def test_an_owned_worker_at_another_commit_is_redeployed() -> None:
    worker = "example-site-prod"
    observed = deployed(worker, marker_for(worker, commit=OLD_COMMIT))
    plan = changes.compare(inputs(), "acme", {worker: observed}, None)
    assert (plan.component("site").worker_part, plan.component("site").deploy) == ("update", True)
    assert changes.apply_steps(plan) == (Step("deploy", "site"),)
    assert changes.summary_lines(plan, applied=False) == ["site: would update Worker example-site-prod"]


def test_a_changed_translation_redeploys() -> None:
    worker = "example-site-prod"
    stale = static_site.marker(PROJECT, COMMIT, "000000000000")
    plan = changes.compare(inputs(), "acme", {worker: deployed(worker, stale)}, None)
    assert plan.component("site").deploy is True


@pytest.mark.parametrize(("workers_dev", "previews"), [(False, False), (True, True)])
def test_an_owned_worker_with_the_wrong_subdomain_settings_is_only_enabled(workers_dev: bool, previews: bool) -> None:
    worker = "example-site-prod"
    observed = deployed(worker, marker_for(worker), workers_dev=workers_dev, previews=previews)
    plan = changes.compare(inputs(), "acme", {worker: observed}, None)
    change = plan.component("site")
    assert (change.worker_part, change.deploy, change.enable) == ("update", False, True)
    assert changes.apply_steps(plan) == (Step("enable", "site"),)


def test_the_owner_is_the_newest_marked_deployment_so_a_hand_rollback_does_not_orphan_it() -> None:
    worker = "example-site-prod"
    observed = deployed(worker, marker_for(worker), None)
    plan = changes.compare(inputs(), "acme", {worker: observed}, None)
    assert plan.component("site").worker_part == "update"


def test_a_worker_owned_by_another_project_is_refused_with_the_whole_line() -> None:
    worker = "example-site-prod"
    other = f"{ORG}/example-site"
    observed = deployed(worker, marker_for(worker, project=other))
    with pytest.raises(Refusal) as caught:
        changes.compare(inputs(), "acme", {worker: observed}, None)
    assert f"site: Worker {worker} belongs to {other}" in str(caught.value).splitlines()
    assert "rename the component" in str(caught.value)


def test_a_newer_marker_of_another_project_owns_the_worker() -> None:
    worker = "example-site-prod"
    observed = deployed(worker, marker_for(worker), marker_for(worker, project=f"{ORG}/example-site"))
    with pytest.raises(Refusal):
        changes.compare(inputs(), "acme", {worker: observed}, None)


def test_a_worker_with_no_plane_marker_is_refused_pointing_to_the_runbook() -> None:
    worker = "example-site-prod"
    with pytest.raises(Refusal) as caught:
        changes.compare(inputs(), "acme", {worker: deployed(worker, None, "by hand")}, None)
    assert f"site: Worker {worker} was not deployed by the plane" in str(caught.value).splitlines()
    assert "docs/cleanup.md" in str(caught.value)


def test_every_refused_component_has_its_own_line() -> None:
    plan_inputs = inputs(names=("one", "two", "three"))
    workers = {
        "example-one-prod": deployed("example-one-prod", None),
        "example-two-prod": deployed("example-two-prod", marker_for("example-two-prod", project=f"{ORG}/x")),
        "example-three-prod": ABSENT,
    }
    with pytest.raises(Refusal) as caught:
        changes.compare(plan_inputs, "acme", workers, None)
    lines = str(caught.value).splitlines()
    assert "one: Worker example-one-prod was not deployed by the plane" in lines
    assert f"two: Worker example-two-prod belongs to {ORG}/x" in lines
    assert not any(line.startswith("three:") for line in lines)


# --- dev and staging ------------------------------------------------------------------------------------------


def test_a_new_private_worker_is_deployed_closed_then_protected_then_opened_after_the_wait() -> None:
    worker = "example-site-dev"
    plan = changes.compare(inputs("dev"), "acme", {worker: ABSENT}, observed_access(existing_policies=()))
    assert [(policy.name, policy.part) for policy in plan.policies] == [
        ("orc-plane-service-token", "create"),
        ("orc-plane-owner", "create"),
    ]
    assert changes.apply_steps(plan) == (
        Step("policy", "orc-plane-service-token"),
        Step("policy", "orc-plane-owner"),
        Step("deploy", "site", workers_dev=False),
        Step("app", "site"),
        Step("wait", seconds=30),
        Step("enable", "site"),
    )
    assert changes.summary_lines(plan, applied=False) == [
        "Access policy orc-plane-service-token: would create",
        "Access policy orc-plane-owner: would create",
        f"site: would create Worker {worker}, would create Access application {worker}",
    ]


def test_no_step_makes_a_private_worker_reachable_before_its_application_and_the_wait() -> None:
    names = ("one", "two", "three")
    workers = {
        "example-one-dev": ABSENT,
        "example-two-dev": deployed("example-two-dev", marker_for("example-two-dev", commit=OLD_COMMIT)),
        "example-three-dev": deployed("example-three-dev", marker_for("example-three-dev"), workers_dev=False),
    }
    plan = changes.compare(inputs("dev", names=names), "acme", workers, observed_access())
    steps = changes.apply_steps(plan)
    for name in names:
        app = steps.index(Step("app", name))
        opening = [i for i, step in enumerate(steps) if step.target == name and step.action in ("enable", "deploy")]
        opening = [i for i in opening if steps[i].action == "enable" or steps[i].workers_dev]
        assert opening and all(i > app for i in opening), (name, steps)
        assert all(i > steps.index(Step("wait", seconds=30)) for i in opening)
    assert sum(step.action == "wait" for step in steps) == 1


def test_a_settled_private_worker_with_its_application_is_unchanged() -> None:
    worker = "example-site-dev"
    plan = changes.compare(
        inputs("dev"), "acme", {worker: deployed(worker, marker_for(worker))}, observed_access((app_for(worker),))
    )
    assert plan.component("site").unchanged
    assert changes.apply_steps(plan) == ()
    assert changes.summary_lines(plan, applied=True) == [
        "Access policy orc-plane-service-token: unchanged",
        "Access policy orc-plane-owner: unchanged",
        "site: unchanged",
    ]


def test_an_application_deleted_by_hand_is_recreated_without_a_wait_when_nothing_opens() -> None:
    worker = "example-site-dev"
    plan = changes.compare(inputs("dev"), "acme", {worker: deployed(worker, marker_for(worker))}, observed_access())
    assert plan.component("site").app_part == "create"
    assert changes.apply_steps(plan) == (Step("app", "site"),)
    assert changes.summary_lines(plan, applied=False)[-1] == f"site: would create Access application {worker}"


def test_an_application_that_differs_is_updated_in_place() -> None:
    worker = "example-site-dev"
    app = app_for(worker, allowed_idps=[])
    plan = changes.compare(
        inputs("dev"), "acme", {worker: deployed(worker, marker_for(worker))}, observed_access((app,))
    )
    change = plan.component("site")
    assert (change.app_part, change.app_id) == ("update", f"app-{worker}")


def test_an_application_found_by_the_script_tag_is_recognised() -> None:
    worker = "example-site-dev"
    app = app_for(worker, destinations=[{"type": "worker", "worker_id": f"tag-{worker}"}])
    plan = changes.compare(
        inputs("dev"), "acme", {worker: deployed(worker, marker_for(worker))}, observed_access((app,))
    )
    assert plan.component("site").app_id == f"app-{worker}"


def test_two_applications_for_one_worker_are_refused() -> None:
    worker = "example-site-dev"
    apps = (app_for(worker), {**app_for(worker), "id": "app-2"})
    with pytest.raises(Refusal) as caught:
        changes.compare(inputs("dev"), "acme", {worker: deployed(worker, marker_for(worker))}, observed_access(apps))
    assert worker in str(caught.value)
    assert "docs/cleanup.md" in str(caught.value)


def test_a_rotated_service_token_updates_the_shared_policy_and_then_every_application() -> None:
    worker = "example-site-dev"
    access = ObservedAccess(
        policies=policies(token_id="old-token"),
        apps=(app_for(worker),),
        service_tokens=(TOKEN,),
        identity_providers=(PIN,),
    )
    plan = changes.compare(inputs("dev"), "acme", {worker: deployed(worker, marker_for(worker))}, access)
    assert plan.policy("orc-plane-service-token").part == "update"
    assert plan.policy("orc-plane-service-token").policy_id == "pol-svc"
    assert plan.policy("orc-plane-owner").part == "unchanged"
    assert plan.component("site").app_part == "unchanged"


def test_missing_policies_mean_every_existing_application_is_updated() -> None:
    worker = "example-site-dev"
    plan = changes.compare(
        inputs("dev"),
        "acme",
        {worker: deployed(worker, marker_for(worker))},
        observed_access((app_for(worker),), existing_policies=()),
    )
    assert plan.component("site").app_part == "update"


def test_the_owner_check_comes_before_access_so_another_projects_application_is_never_touched() -> None:
    worker = "example-site-dev"
    observed = deployed(worker, marker_for(worker, project=f"{ORG}/other"))
    access = ObservedAccess(policies=(), apps=(), service_tokens=(), identity_providers=())
    with pytest.raises(Refusal) as caught:
        changes.compare(inputs("dev"), "acme", {worker: observed}, access)
    assert "belongs to" in str(caught.value)


def test_a_missing_service_token_is_refused() -> None:
    access = ObservedAccess(policies=(), apps=(), service_tokens=(), identity_providers=(PIN,))
    with pytest.raises(Refusal, match="orc-plane-tests"):
        changes.compare(inputs("staging"), "acme", {"example-site-staging": ABSENT}, access)


# --- results --------------------------------------------------------------------------------------------------


def test_header_names_env_mode_project_and_commit() -> None:
    assert changes.header(inputs("dev", "apply")) == f"dev apply for {PROJECT} at {COMMIT}"


def test_live_components_after_a_failure_are_those_with_no_step_left() -> None:
    workers = {
        "example-one-prod": ABSENT,
        "example-two-prod": ABSENT,
        "example-three-prod": deployed("example-three-prod", marker_for("example-three-prod")),
    }
    plan = changes.compare(inputs(names=("one", "two", "three")), "acme", workers, None)
    steps = changes.apply_steps(plan)
    assert [component.name for component in changes.live_components(plan, steps, 1)] == ["one", "three"]
    assert [component.name for component in changes.live_components(plan, steps, len(steps))] == ["one", "two", "three"]


def test_a_failed_shared_policy_leaves_only_unchanged_components_live() -> None:
    workers = {"example-one-dev": ABSENT, "example-two-dev": deployed("example-two-dev", marker_for("example-two-dev"))}
    access = observed_access((app_for("example-two-dev"),), existing_policies=policies(email="old@example.com"))
    plan = changes.compare(inputs("dev", names=("one", "two")), "acme", workers, access)
    steps = changes.apply_steps(plan)
    assert steps[0] == Step("policy", "orc-plane-owner")
    assert [component.name for component in changes.live_components(plan, steps, 0)] == ["two"]
