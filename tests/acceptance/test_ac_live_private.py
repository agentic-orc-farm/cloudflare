"""AC35 to AC42: dev and staging behind Cloudflare Access. Live only.

Before AC35 the `private_from_nothing` fixture removes the dev and staging fixture Workers' Access applications,
then the Workers, so every run starts from nothing. It never removes the shared policies or the service token.
Failure messages give counts and names only: the owner's email and Access bodies stay out of the public log.
"""

from tests.acceptance.helpers import Live, Step, get

SERVICE_TOKEN_POLICY = "orc-plane-service-token"
OWNER_POLICY = "orc-plane-owner"
SERVICE_TOKEN = "orc-plane-tests"


def test_AC35_plan_to_dev_reports_worker_and_access_application_and_creates_nothing(live: Live, dev_plan: Step) -> None:
    run = dev_plan.run
    assert run.exit_code == 0, run.describe()
    assert run.lists("fixture-web", dev_plan.url), f"fixture-web should be listed at {dev_plan.url}\n{run.describe()}"
    line = f"fixture-web: would create Worker {dev_plan.worker}, would create Access application {dev_plan.worker}"
    assert line in run.summary_lines, f"the summary lacks the line {line!r}\n{run.describe()}"
    assert dev_plan.worker_present_after is False, f"the plan created the Worker {dev_plan.worker}"
    assert dev_plan.apps_after == 0, f"the plan created {dev_plan.apps_after} Access application(s)"


def test_AC36_apply_to_dev_serves_the_commit_to_requests_with_the_headers(live: Live, dev_first_apply: Step) -> None:
    run = dev_first_apply.run
    assert run.exit_code == 0, run.describe()
    assert run.lists("fixture-web", dev_first_apply.url), run.describe()
    assert dev_first_apply.reached_with_headers, (
        f"{dev_first_apply.url}/commit.txt with the headers did not serve the fixture commit within 120 seconds; "
        f"last: {dev_first_apply.reached_detail}"
    )


def test_AC37_without_the_headers_never_200_through_the_apply(live: Live, dev_first_apply: Step) -> None:
    assert dev_first_apply.apply_started is not None and dev_first_apply.apply_ended is not None
    observations = dev_first_apply.unauthorised_observations
    window = dev_first_apply.apply_ended + 30 - dev_first_apply.apply_started
    assert len(observations) >= min(30, int(window * 0.8)), f"only {len(observations)} requests in {window:.0f} seconds"
    assert observations[0][0] <= dev_first_apply.apply_started, "polling began after the apply started"
    assert observations[-1][0] >= dev_first_apply.apply_ended + 28, "polling stopped before 30 seconds after the apply"
    answered_after = [status for began, status in observations if began > dev_first_apply.apply_ended and status]
    assert answered_after, "the address never answered after the apply, so the check proves nothing"
    reached = [round(began - dev_first_apply.apply_started) for began, status in observations if status == 200]
    assert not reached, f"a request without the headers got 200 at these seconds from the apply's start: {reached}"


def test_AC38_without_the_headers_the_commit_is_not_served(live: Live, dev_first_apply: Step) -> None:
    assert dev_first_apply.run.exit_code == 0, dev_first_apply.run.describe()
    response = get(f"{dev_first_apply.url}/commit.txt")
    assert response is not None, "the request failed outright; expected Access to answer"
    assert response.status_code != 200, "a request without the headers got 200"
    assert live.commit not in response.text, "a request without the headers got the fixture commit"


def _one_named(items: list[dict], name: str, what: str) -> dict:
    found = [item for item in items if item.get("name") == name]
    assert len(found) == 1, f"expected exactly one {what} named {name}, found {len(found)}"
    return found[0]


def test_AC39_dev_worker_has_one_access_application_with_the_two_shared_policies(
    live: Live, dev_first_apply: Step
) -> None:
    assert dev_first_apply.run.exit_code == 0, dev_first_apply.run.describe()
    worker = dev_first_apply.worker
    apps = live.cloudflare.apps_for_worker(worker, live.hostname(worker))
    assert len(apps) == 1, f"expected exactly one Access application for {worker}, found {len(apps)}"
    app = apps[0]

    policies = live.cloudflare.reusable_policies()
    service_policy = _one_named(policies, SERVICE_TOKEN_POLICY, "reusable policy")
    owner_policy = _one_named(policies, OWNER_POLICY, "reusable policy")
    app_policy_ids = [policy.get("id") for policy in app.get("policies") or []]
    assert sorted(app_policy_ids) == sorted([service_policy.get("id"), owner_policy.get("id")]), (
        f"the application's {len(app_policy_ids)} policies are not exactly {SERVICE_TOKEN_POLICY} and {OWNER_POLICY}"
    )

    assert service_policy.get("decision") == "non_identity", f"{SERVICE_TOKEN_POLICY} decision is not non_identity"
    token = _one_named(live.cloudflare.service_tokens(), SERVICE_TOKEN, "service token")
    includes_token = any(
        (rule.get("service_token") or {}).get("token_id") == token.get("id")
        for rule in service_policy.get("include") or []
    )
    assert includes_token, f"{SERVICE_TOKEN_POLICY} does not include the service token {SERVICE_TOKEN}"

    assert owner_policy.get("decision") == "allow", f"{OWNER_POLICY} decision is not allow"
    includes_owner = any(
        str((rule.get("email") or {}).get("email", "")).lower() == live.owner_email.lower()
        for rule in owner_policy.get("include") or []
    )
    assert includes_owner, f"{OWNER_POLICY} does not include the email in ACCESS_OWNER_EMAIL"

    one_time_pin = [idp.get("id") for idp in live.cloudflare.identity_providers() if idp.get("type") == "onetimepin"]
    assert len(one_time_pin) == 1, f"expected the account to have one one-time PIN provider, found {len(one_time_pin)}"
    allowed = app.get("allowed_idps") or []
    assert allowed == one_time_pin, f"the application allows {len(allowed)} provider(s), not only the one-time PIN"


def test_AC40_second_apply_to_dev_changes_nothing_and_duplicates_nothing(
    live: Live, dev_first_apply: Step, dev_second_apply: Step
) -> None:
    run = dev_second_apply.run
    assert run.exit_code == 0, run.describe()
    assert "fixture-web: unchanged" in run.summary_lines, run.describe()
    assert dev_first_apply.deployment_after is not None, "the first apply left no active deployment"
    assert dev_second_apply.deployment_after == dev_first_apply.deployment_after, (
        "the second apply changed the Worker's active deployment"
    )
    assert dev_second_apply.apps_after == 1, f"{dev_second_apply.apps_after} Access applications for the Worker"
    assert dev_second_apply.policies_after == {SERVICE_TOKEN_POLICY: 1, OWNER_POLICY: 1}, (
        f"reusable policies by name: {dev_second_apply.policies_after}"
    )


def test_AC41_dev_worker_has_workers_dev_on_and_previews_off(live: Live, dev_second_apply: Step) -> None:
    assert dev_second_apply.run.exit_code == 0, dev_second_apply.run.describe()
    settings = live.cloudflare.script_subdomain(dev_second_apply.worker)
    assert settings.get("enabled") is True, f"workers.dev is not enabled: {settings}"
    assert settings.get("previews_enabled") is False, f"previews are not disabled: {settings}"


def test_AC42_plan_to_staging_reports_worker_and_access_application_and_creates_nothing(
    live: Live, staging_plan: Step
) -> None:
    run = staging_plan.run
    assert run.exit_code == 0, run.describe()
    assert run.lists("fixture-web", staging_plan.url), run.describe()
    line = (
        f"fixture-web: would create Worker {staging_plan.worker}, would create Access application {staging_plan.worker}"
    )
    assert line in run.summary_lines, f"the summary lacks the line {line!r}\n{run.describe()}"
    assert staging_plan.worker_present_after is False, f"the plan created the Worker {staging_plan.worker}"
