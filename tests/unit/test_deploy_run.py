"""`run_deploy` end to end over the fake Cloudflare, GitHub and wrangler: what the account holds afterwards."""

import json

import pytest
from tests.helpers import COMMIT, ORG, OWNER_EMAIL, PROJECT, read_wrangler_log

from cf_plane import changes, static_site
from cf_plane.cli import run_deploy

SITE = {"name": "site", "kind": "static-site", "plane": "cloudflare", "artefact": "site-bundle"}
FILES = {"index.html": "home", "404.html": "missing", "commit.txt": COMMIT}
OTHER_COMMIT = "c" * 40


def inputs(env: str = "prod", mode: str = "apply", *, commit: str = COMMIT, project: str = PROJECT, items=(SITE,)):
    return changes.validate(
        project=project,
        commit=commit,
        env=env,
        mode=mode,
        components=json.dumps(list(items)),
        plane_org=ORG,
        owner_email=OWNER_EMAIL,
    )


def run(world, *args, **kwargs):
    result, code = run_deploy(inputs(*args, **kwargs), world.services(), world.scratch())
    return json.loads(result.to_json()), code


def lines(result: dict) -> list[str]:
    return result["summary"].splitlines()


# --- prod -----------------------------------------------------------------------------------------------------


def test_a_prod_plan_reports_the_address_and_changes_nothing(world) -> None:
    world.read_token = None
    result, code = run(world, "prod", "plan")
    assert code == 0
    assert result["components"] == [{"name": "site", "url": "https://example-site-prod.acme.workers.dev"}]
    assert lines(result) == [f"prod plan for {PROJECT} at {COMMIT}", "site: would create Worker example-site-prod"]
    assert world.cloudflare.effects == []
    assert "example-site-prod" not in world.cloudflare.scripts


def test_a_prod_apply_deploys_the_artefact_publicly_with_the_marker(world) -> None:
    world.github.add("site-bundle", FILES)
    result, code = run(world)
    assert code == 0, result
    assert result["components"] == [{"name": "site", "url": "https://example-site-prod.acme.workers.dev"}]
    assert lines(result)[-1] == "site: created Worker example-site-prod"
    script = world.cloudflare.scripts["example-site-prod"]
    assert script.files == FILES
    assert (script.workers_dev, script.previews) == (True, False)
    [record] = read_wrangler_log(world.wrangler_log)
    assert record["message"] == static_site.desired_marker(PROJECT, COMMIT, "example-site-prod")
    assert record["leaked"] == []
    assert world.cloudflare.apps == []
    assert world.cloudflare.policies == []


def test_a_second_apply_and_a_plan_change_nothing(world) -> None:
    world.github.add("site-bundle", FILES)
    run(world)
    deployment = world.cloudflare.active_deployment("example-site-prod")
    world.read_token = None
    for mode in ("apply", "plan"):
        result, code = run(world, "prod", mode)
        assert code == 0
        assert "site: unchanged" in lines(result)
        assert result["components"] == [{"name": "site", "url": "https://example-site-prod.acme.workers.dev"}]
    assert world.cloudflare.active_deployment("example-site-prod") == deployment
    assert len(read_wrangler_log(world.wrangler_log)) == 1


def test_an_apply_of_another_commit_updates_the_worker(world) -> None:
    world.github.add("site-bundle", FILES)
    world.github.add("site-bundle", {**FILES, "commit.txt": OTHER_COMMIT}, commit=OTHER_COMMIT)
    run(world)
    result, code = run(world, commit=OTHER_COMMIT)
    assert code == 0
    assert lines(result)[-1] == "site: updated Worker example-site-prod"
    assert world.cloudflare.scripts["example-site-prod"].files["commit.txt"] == OTHER_COMMIT


def test_an_apply_without_the_artefact_fails_naming_it_and_the_commit_and_changes_nothing(world) -> None:
    world.github.add("site-bundle", FILES)
    run(world)
    deployment = world.cloudflare.active_deployment("example-site-prod")
    zeros = "0" * 40
    result, code = run(world, commit=zeros)
    assert code == 1
    assert result["components"] == []
    assert "site-bundle" in result["summary"]
    assert zeros in result["summary"]
    assert world.cloudflare.active_deployment("example-site-prod") == deployment


def test_an_apply_without_the_read_token_is_refused_before_any_change(world) -> None:
    world.read_token = None

    def no_token():
        from cf_plane.cli import _read_token

        return _read_token({})

    services = world.services()
    services.github = no_token
    result, code = run_deploy(inputs(), services, world.scratch())
    assert code == 1
    assert "GITHUB_READ_TOKEN" in result.summary
    assert result.components == ()
    assert world.cloudflare.effects == []


@pytest.mark.parametrize("mode", ["plan", "apply"])
def test_a_worker_another_project_owns_is_refused_and_left_alone(world, mode: str) -> None:
    world.github.add("site-bundle", FILES, project=f"{ORG}/example-fixture")
    owner_marker = static_site.desired_marker(PROJECT, COMMIT, "example-fixture-web-prod")
    world.cloudflare.add_script("example-fixture-web-prod", owner_marker)
    deployment = world.cloudflare.active_deployment("example-fixture-web-prod")
    web = {**SITE, "name": "fixture-web"}
    asking = {**SITE, "name": "web"}
    result, code = run(world, "prod", mode, project=f"{ORG}/example", items=(web,))
    assert code == 0
    result, code = run(world, "prod", mode, project=f"{ORG}/example-fixture", items=(asking,))
    assert code == 1
    assert result["components"] == []
    assert f"web: Worker example-fixture-web-prod belongs to {PROJECT}" in lines(result)
    assert world.cloudflare.active_deployment("example-fixture-web-prod") == deployment


def test_a_failed_wrangler_lists_only_the_components_already_live(world) -> None:
    one, two = {**SITE, "name": "one"}, {**SITE, "name": "two"}
    world.github.add("site-bundle", FILES)
    world.cloudflare.add_script("example-two-prod", static_site.desired_marker(PROJECT, COMMIT, "example-two-prod"))
    world.wrangler_environment = {**world.wrangler_environment, "FAKE_WRANGLER_EXIT": "1"}
    result, code = run(world, items=(one, two))
    assert code == 1
    assert result["components"] == [{"name": "two", "url": "https://example-two-prod.acme.workers.dev"}]
    assert "one: failed: wrangler deploy of example-one-prod exited 1" in result["summary"]


# --- dev and staging ------------------------------------------------------------------------------------------


def test_a_dev_plan_reports_the_worker_and_application_and_creates_nothing(world) -> None:
    world.read_token = None
    result, code = run(world, "dev", "plan")
    assert code == 0
    assert lines(result) == [
        f"dev plan for {PROJECT} at {COMMIT}",
        "Access policy orc-plane-service-token: would create",
        "Access policy orc-plane-owner: would create",
        "site: would create Worker example-site-dev, would create Access application example-site-dev",
    ]
    assert world.cloudflare.effects == []


def test_a_dev_apply_never_opens_the_worker_before_its_application_has_had_time(world) -> None:
    world.github.add("site-bundle", FILES)
    result, code = run(world, "dev")
    assert code == 0, result
    assert world.cloudflare.effects == [
        "create policies orc-plane-service-token",
        "create policies orc-plane-owner",
        "deploy example-site-dev workers_dev=False",
        "create apps example-site-dev",
        "wait 30",
        "enable example-site-dev",
    ]
    script = world.cloudflare.scripts["example-site-dev"]
    assert (script.workers_dev, script.previews) == (True, False)
    [app] = world.cloudflare.apps_for("example-site-dev")
    assert app["destinations"] == [{"type": "worker", "worker_id": "wid-example-site-dev"}]
    assert [policy["name"] for policy in sorted(app["policies"], key=lambda p: p["precedence"])] == [
        "orc-plane-service-token",
        "orc-plane-owner",
    ]
    assert app["allowed_idps"] == ["pin-1"]
    [service] = world.cloudflare.policy_named("orc-plane-service-token")
    assert service["include"] == [{"service_token": {"token_id": "tok-1"}}]
    [owner] = world.cloudflare.policy_named("orc-plane-owner")
    assert owner["include"] == [{"email": {"email": OWNER_EMAIL}}]
    assert lines(result)[-1] == "site: created Worker example-site-dev, created Access application example-site-dev"


def test_a_second_dev_apply_changes_and_duplicates_nothing(world) -> None:
    world.github.add("site-bundle", FILES)
    run(world, "dev")
    deployment = world.cloudflare.active_deployment("example-site-dev")
    effects = len(world.cloudflare.effects)
    result, code = run(world, "dev")
    assert code == 0
    assert "site: unchanged" in lines(result)
    assert world.cloudflare.effects[effects:] == []
    assert world.cloudflare.active_deployment("example-site-dev") == deployment
    assert len(world.cloudflare.apps_for("example-site-dev")) == 1
    assert len(world.cloudflare.policy_named("orc-plane-owner")) == 1


def test_a_staging_worker_shares_the_dev_policies(world) -> None:
    world.github.add("site-bundle", FILES)
    run(world, "dev")
    result, code = run(world, "staging")
    assert code == 0
    assert "Access policy orc-plane-owner: unchanged" in lines(result)
    assert len(world.cloudflare.policies) == 2
    assert len(world.cloudflare.apps) == 2


def test_a_private_redeploy_fixes_the_application_before_deploying(world) -> None:
    world.github.add("site-bundle", FILES)
    world.github.add("site-bundle", {**FILES, "commit.txt": OTHER_COMMIT}, commit=OTHER_COMMIT)
    run(world, "dev")
    world.cloudflare.apps.clear()
    effects = len(world.cloudflare.effects)
    result, code = run(world, "dev", commit=OTHER_COMMIT)
    assert code == 0
    assert world.cloudflare.effects[effects:] == [
        "create apps example-site-dev",
        "wait 30",
        "deploy example-site-dev workers_dev=True",
    ]
    assert lines(result)[-1] == "site: updated Worker example-site-dev, created Access application example-site-dev"


def test_an_apply_left_part_way_is_finished_by_running_it_again(world) -> None:
    world.github.add("site-bundle", FILES)
    world.cloudflare.fail = {("POST", "/access/apps"): 500}
    result, code = run(world, "dev")
    assert code == 1
    assert result["components"] == []
    script = world.cloudflare.scripts["example-site-dev"]
    assert script.workers_dev is False, "a Worker left part way is at no address"
    world.cloudflare.fail = {}
    result, code = run(world, "dev")
    assert code == 0
    assert lines(result)[-1] == "site: updated Worker example-site-dev, created Access application example-site-dev"
    assert (script.workers_dev, script.previews) == (True, False)
    assert len(read_wrangler_log(world.wrangler_log)) == 1


def test_a_cloudflare_failure_while_observing_is_a_refusal(world) -> None:
    world.cloudflare.fail = {("GET", "/workers/scripts"): 403}
    result, code = run(world, "prod", "plan")
    assert code == 1
    assert result["components"] == []
    assert "403" in result["summary"]
