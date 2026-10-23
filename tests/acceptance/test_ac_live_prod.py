"""AC15 to AC22, AC29, AC30 and AC43: plan and apply to prod against Cloudflare. Live only.

They run only in the `acceptance` workflow (ACCEPTANCE_LIVE=1). The fixture project is this repository, and its
`fixture-site` artefact is the one ci.yml uploaded for ACCEPTANCE_COMMIT.
"""

from tests.acceptance.helpers import FIXTURE_SITE, NO_ARTEFACTS_COMMIT, Live, Step, wait_for


def test_AC15_plan_reports_a_new_worker_and_creates_nothing(live: Live, prod_plan_only: Step) -> None:
    run = prod_plan_only.run
    assert run.exit_code == 0, run.describe()
    assert run.lists("plan-only", prod_plan_only.url), (
        f"plan-only should be listed at {prod_plan_only.url}\n{run.describe()}"
    )
    line = f"plan-only: would create Worker {prod_plan_only.worker}"
    assert line in run.summary_lines, f"the summary lacks the line {line!r}\n{run.describe()}"
    assert prod_plan_only.worker_present_after is False, f"the plan created the Worker {prod_plan_only.worker}"


def test_AC16_plan_needs_no_read_token_and_no_artefacts(live: Live, prod_plan_no_artefacts: Step) -> None:
    run = prod_plan_no_artefacts.run
    assert run.exit_code == 0, run.describe()
    assert run.lists("site", prod_plan_no_artefacts.url), (
        f"site should be listed at {prod_plan_no_artefacts.url}\n{run.describe()}"
    )


def test_AC17_apply_deploys_the_fixture_commit_publicly(live: Live, prod_first_apply: Step) -> None:
    run = prod_first_apply.run
    assert run.exit_code == 0, run.describe()
    assert run.lists("fixture-web", prod_first_apply.url), (
        f"fixture-web should be listed at {prod_first_apply.url}\n{run.describe()}"
    )
    served, last = wait_for(
        f"{prod_first_apply.url}/commit.txt",
        lambda response: response.status_code == 200 and response.text.strip() == live.commit,
        seconds=120,
    )
    assert served, (
        f"{prod_first_apply.url}/commit.txt did not serve the fixture commit within 120 seconds; last: {last}"
    )


def test_AC18_missing_page_is_the_fixture_404_page(live: Live, prod_first_apply: Step) -> None:
    assert prod_first_apply.run.exit_code == 0, prod_first_apply.run.describe()
    expected = (FIXTURE_SITE / "404.html").read_text().strip()
    found, last = wait_for(
        f"{prod_first_apply.url}/no-such-page",
        lambda response: response.status_code == 404 and response.text.strip() == expected,
        seconds=120,
    )
    assert found, f"{prod_first_apply.url}/no-such-page did not return 404 with the fixture's 404.html; last: {last}"


def test_AC19_prod_worker_has_workers_dev_on_and_previews_off(live: Live, prod_first_apply: Step) -> None:
    assert prod_first_apply.run.exit_code == 0, prod_first_apply.run.describe()
    settings = live.cloudflare.script_subdomain(prod_first_apply.worker)
    assert settings.get("enabled") is True, f"workers.dev is not enabled: {settings}"
    assert settings.get("previews_enabled") is False, f"previews are not disabled: {settings}"


def test_AC43_prod_worker_has_no_access_application(live: Live, prod_first_apply: Step) -> None:
    assert prod_first_apply.run.exit_code == 0, prod_first_apply.run.describe()
    worker = prod_first_apply.worker
    apps = live.cloudflare.apps_for_worker(worker, live.hostname(worker))
    assert not apps, f"{len(apps)} Access application(s) protect the public Worker {worker}"


def test_AC20_second_apply_changes_nothing(live: Live, prod_first_apply: Step, prod_second_apply: Step) -> None:
    run = prod_second_apply.run
    assert run.exit_code == 0, run.describe()
    assert run.lists("fixture-web", prod_first_apply.url), run.describe()
    assert "fixture-web: unchanged" in run.summary_lines, run.describe()
    assert prod_first_apply.deployment_after is not None, "the first apply left no active deployment"
    assert prod_second_apply.deployment_after == prod_first_apply.deployment_after, (
        "the second apply changed the Worker's active deployment"
    )


def test_AC21_plan_after_apply_says_unchanged(live: Live, prod_plan_after_apply: Step) -> None:
    run = prod_plan_after_apply.run
    assert run.exit_code == 0, run.describe()
    assert "fixture-web: unchanged" in run.summary_lines, run.describe()
    assert prod_plan_after_apply.deployment_before is not None, "there was no active deployment before the plan"
    assert prod_plan_after_apply.deployment_after == prod_plan_after_apply.deployment_before, (
        "the plan changed the Worker's active deployment"
    )


def test_AC22_apply_without_the_artefact_fails_and_changes_nothing(live: Live, prod_failed_apply: Step) -> None:
    run = prod_failed_apply.run
    assert run.exit_code != 0, run.describe()
    assert "fixture-site" in run.summary, f"the summary does not name the artefact\n{run.describe()}"
    assert NO_ARTEFACTS_COMMIT in run.summary, f"the summary does not name the commit\n{run.describe()}"
    assert prod_failed_apply.deployment_before is not None, "there was no active deployment before the apply"
    assert prod_failed_apply.deployment_after == prod_failed_apply.deployment_before, (
        "the failed apply changed the Worker's active deployment"
    )


def _owner_line(live: Live, step: Step) -> str:
    return f"web: Worker {step.worker} belongs to {live.project}"


def test_AC29_apply_onto_a_worker_another_project_owns_is_refused(live: Live, collision_apply: Step) -> None:
    run = collision_apply.run
    assert run.exit_code != 0, run.describe()
    assert run.result_problem is None, run.describe()
    assert isinstance(run.result, dict) and run.result.get("components") == [], run.describe()
    assert _owner_line(live, collision_apply) in run.summary_lines, run.describe()
    assert collision_apply.deployment_before is not None, "there was no active deployment before the apply"
    assert collision_apply.deployment_after == collision_apply.deployment_before, (
        "the refused apply changed the Worker's active deployment"
    )


def test_AC30_plan_onto_a_worker_another_project_owns_is_refused(live: Live, collision_plan: Step) -> None:
    run = collision_plan.run
    assert run.exit_code != 0, run.describe()
    assert run.result_problem is None, run.describe()
    assert isinstance(run.result, dict) and run.result.get("components") == [], run.describe()
    assert _owner_line(live, collision_plan) in run.summary_lines, run.describe()


def test_AC18_fixture_has_a_404_page_whose_text_no_other_file_holds() -> None:
    """Offline: the fixture AC17 and AC18 deploy has an index.html, and a 404.html no other file can pass for."""
    files = sorted(path.name for path in FIXTURE_SITE.iterdir())
    assert files == ["404.html", "index.html"], files
    marker = "fixture-not-found-page-5d81c2e7"
    assert marker in (FIXTURE_SITE / "404.html").read_text()
    assert marker not in (FIXTURE_SITE / "index.html").read_text()
