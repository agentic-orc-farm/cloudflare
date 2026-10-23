"""Fixtures for the acceptance tests. The helpers they use live in tests/acceptance/helpers.py.

The live fixtures are session-scoped steps chained by their dependencies, so each plan or apply runs once, in
the order the criteria describe, whatever order pytest runs the tests in. Run the live criteria in one process
(no `-n`): two processes would each run the steps.
"""

import os
import time
from collections.abc import Callable

import pytest
from tests.acceptance.helpers import (
    LIVE_SKIP_REASON,
    LIVE_VARIABLES,
    NO_ARTEFACTS_COMMIT,
    Cloudflare,
    Live,
    Poller,
    Refusal,
    Run,
    Step,
    deploy_arguments,
    fixture_component,
    get,
    offline_environment,
    run_cf_plane,
)

PRIVATE_POLICIES = ("orc-plane-service-token", "orc-plane-owner")


@pytest.fixture(scope="session")
def refused(tmp_path_factory: pytest.TempPathFactory) -> Callable[[Refusal], Run]:
    """Runs a refusal case once per session, with no credentials, and returns the run."""
    folder = tmp_path_factory.mktemp("refusals")
    runs: dict[str, Run] = {}

    def run(case: Refusal) -> Run:
        if case.case not in runs:
            result_path = folder / f"{case.case}-result.json"
            arguments = deploy_arguments(
                project=case.project,
                commit=case.commit,
                env=case.env,
                mode=case.mode,
                components=case.components,
                result_path=result_path,
            )
            runs[case.case] = run_cf_plane(arguments, offline_environment(), result_path)
        return runs[case.case]

    return run


@pytest.fixture(scope="session")
def live(tmp_path_factory: pytest.TempPathFactory) -> Live:
    if os.environ.get("ACCEPTANCE_LIVE") != "1":
        pytest.skip(LIVE_SKIP_REASON)
    missing = [name for name in LIVE_VARIABLES if not os.environ.get(name)]
    if missing:
        pytest.fail("the live acceptance criteria need these variables, which are missing: " + ", ".join(missing))
    project = os.environ["ACCEPTANCE_PROJECT"]
    environment = dict(os.environ)
    environment.setdefault("PLANE_ORG", project.split("/", 1)[0])
    cloudflare = Cloudflare(os.environ["CLOUDFLARE_API_TOKEN"], os.environ["CLOUDFLARE_ACCOUNT_ID"])
    return Live(
        project=project,
        commit=os.environ["ACCEPTANCE_COMMIT"],
        environment=environment,
        cloudflare=cloudflare,
        subdomain=cloudflare.workers_subdomain(),
        scratch=tmp_path_factory.mktemp("live"),
        access_headers={
            "CF-Access-Client-Id": os.environ["CF_ACCESS_CLIENT_ID"],
            "CF-Access-Client-Secret": os.environ["CF_ACCESS_CLIENT_SECRET"],
        },
        owner_email=os.environ["ACCESS_OWNER_EMAIL"],
    )


# --- prod ---------------------------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def prod_plan_only(live: Live) -> Step:
    """AC15: a plan for a Worker that does not exist. A leftover from an earlier faulty run is removed first."""
    worker = f"{live.repo}-plan-only-prod"
    if live.cloudflare.worker_exists(worker):
        live.cloudflare.delete_worker(worker)
    run = live.deploy("AC15", env="prod", mode="plan", components=fixture_component("plan-only"))
    return Step(run, worker, live.url(worker), worker_present_after=live.cloudflare.worker_exists(worker))


@pytest.fixture(scope="session")
def prod_plan_no_artefacts(live: Live) -> Step:
    """AC16: a plan with no read token, for a commit with no artefacts."""
    worker = f"{live.repo}-site-prod"
    run = live.deploy(
        "AC16",
        env="prod",
        mode="plan",
        components=fixture_component("site", artefact="site"),
        commit=NO_ARTEFACTS_COMMIT,
        without=("GITHUB_READ_TOKEN",),
    )
    return Step(run, worker, live.url(worker))


@pytest.fixture(scope="session")
def prod_first_apply(live: Live) -> Step:
    """AC17: the apply of fixture-web to prod for the fixture commit."""
    worker = f"{live.repo}-fixture-web-prod"
    before = live.cloudflare.active_deployment_id(worker)
    run = live.deploy("AC17", env="prod", mode="apply", components=fixture_component())
    after = live.cloudflare.active_deployment_id(worker)
    return Step(run, worker, live.url(worker), deployment_before=before, deployment_after=after)


@pytest.fixture(scope="session")
def prod_second_apply(live: Live, prod_first_apply: Step) -> Step:
    """AC20: the same apply again."""
    worker = prod_first_apply.worker
    before = live.cloudflare.active_deployment_id(worker)
    run = live.deploy("AC20", env="prod", mode="apply", components=fixture_component())
    after = live.cloudflare.active_deployment_id(worker)
    return Step(run, worker, prod_first_apply.url, deployment_before=before, deployment_after=after)


@pytest.fixture(scope="session")
def prod_plan_after_apply(live: Live, prod_second_apply: Step) -> Step:
    """AC21: a plan with the same inputs after the applies."""
    worker = prod_second_apply.worker
    before = live.cloudflare.active_deployment_id(worker)
    run = live.deploy("AC21", env="prod", mode="plan", components=fixture_component())
    after = live.cloudflare.active_deployment_id(worker)
    return Step(run, worker, prod_second_apply.url, deployment_before=before, deployment_after=after)


@pytest.fixture(scope="session")
def prod_failed_apply(live: Live, prod_plan_after_apply: Step) -> Step:
    """AC22: an apply for a commit with no fixture-site artefact."""
    worker = prod_plan_after_apply.worker
    before = live.cloudflare.active_deployment_id(worker)
    run = live.deploy("AC22", env="prod", mode="apply", components=fixture_component(), commit=NO_ARTEFACTS_COMMIT)
    after = live.cloudflare.active_deployment_id(worker)
    return Step(run, worker, prod_plan_after_apply.url, deployment_before=before, deployment_after=after)


@pytest.fixture(scope="session")
def collision_apply(live: Live, prod_failed_apply: Step) -> Step:
    """AC29: another project asks, by apply, for the Worker name the fixture project holds."""
    worker = prod_failed_apply.worker
    before = live.cloudflare.active_deployment_id(worker)
    run = live.deploy(
        "AC29",
        env="prod",
        mode="apply",
        components=fixture_component("web"),
        project=f"{live.owner}/{live.repo}-fixture",
    )
    after = live.cloudflare.active_deployment_id(worker)
    return Step(run, worker, prod_failed_apply.url, deployment_before=before, deployment_after=after)


@pytest.fixture(scope="session")
def collision_plan(live: Live, collision_apply: Step) -> Step:
    """AC30: the same, by plan."""
    worker = collision_apply.worker
    run = live.deploy(
        "AC30",
        env="prod",
        mode="plan",
        components=fixture_component("web"),
        project=f"{live.owner}/{live.repo}-fixture",
    )
    return Step(run, worker, collision_apply.url)


# --- dev and staging ----------------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def private_from_nothing(live: Live) -> None:
    """Before AC35: remove the private fixture Workers' Access applications, then the Workers themselves."""
    for env in ("dev", "staging"):
        worker = f"{live.repo}-fixture-web-{env}"
        live.cloudflare.remove_worker_and_apps(worker, live.hostname(worker))


def _policy_counts(live: Live) -> dict[str, int]:
    names = [policy.get("name") for policy in live.cloudflare.reusable_policies()]
    return {name: names.count(name) for name in PRIVATE_POLICIES}


@pytest.fixture(scope="session")
def dev_plan(live: Live, private_from_nothing: None) -> Step:
    """AC35: a plan to dev with no dev Worker."""
    worker = f"{live.repo}-fixture-web-dev"
    run = live.deploy("AC35", env="dev", mode="plan", components=fixture_component())
    return Step(
        run,
        worker,
        live.url(worker),
        worker_present_after=live.cloudflare.worker_exists(worker),
        apps_after=len(live.cloudflare.apps_for_worker(worker, live.hostname(worker))),
    )


@pytest.fixture(scope="session")
def dev_first_apply(live: Live, dev_plan: Step) -> Step:
    """AC36 and AC37: the apply that creates the dev Worker, watched without the headers throughout."""
    worker = dev_plan.worker
    url = dev_plan.url
    poller = Poller(f"{url}/commit.txt")
    poller.start()
    time.sleep(1.5)
    started = time.monotonic()
    try:
        run = live.deploy("AC36", env="dev", mode="apply", components=fixture_component())
        ended = time.monotonic()
        reached = False
        detail = "not tried: the apply failed"
        if run.exit_code == 0:
            deadline = ended + 120
            detail = "no response"
            while time.monotonic() < deadline:
                response = get(f"{url}/commit.txt", live.access_headers)
                if response is not None:
                    if response.status_code == 200 and response.text.strip() == live.commit:
                        reached = True
                        detail = f"200 after {time.monotonic() - ended:.0f} seconds"
                        break
                    detail = f"status {response.status_code}"
                time.sleep(2)
        remaining = ended + 30 - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
    finally:
        poller.stop()
    return Step(
        run,
        worker,
        url,
        deployment_after=live.cloudflare.active_deployment_id(worker),
        apply_started=started,
        apply_ended=ended,
        unauthorised_observations=list(poller.observations),
        reached_with_headers=reached,
        reached_detail=detail,
    )


@pytest.fixture(scope="session")
def dev_second_apply(live: Live, dev_first_apply: Step) -> Step:
    """AC40: the same apply to dev again."""
    worker = dev_first_apply.worker
    before = live.cloudflare.active_deployment_id(worker)
    run = live.deploy("AC40", env="dev", mode="apply", components=fixture_component())
    return Step(
        run,
        worker,
        dev_first_apply.url,
        deployment_before=before,
        deployment_after=live.cloudflare.active_deployment_id(worker),
        apps_after=len(live.cloudflare.apps_for_worker(worker, live.hostname(worker))),
        policies_after=_policy_counts(live),
    )


@pytest.fixture(scope="session")
def staging_plan(live: Live, private_from_nothing: None) -> Step:
    """AC42: a plan to staging with no staging Worker."""
    worker = f"{live.repo}-fixture-web-staging"
    run = live.deploy("AC42", env="staging", mode="plan", components=fixture_component())
    return Step(run, worker, live.url(worker), worker_present_after=live.cloudflare.worker_exists(worker))
