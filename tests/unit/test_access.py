import pytest

from cf_plane import access, static_site
from cf_plane.contract import Refusal

TOKEN = {"id": "tok-1", "name": "orc-plane-tests"}
PIN = {"id": "pin-1", "type": "onetimepin", "name": "One-time PIN"}


def test_desired_policies_admit_the_service_token_and_the_owner() -> None:
    service, owner = access.desired_policies("tok-1", "owner@example.com")
    assert service == {
        "name": "orc-plane-service-token",
        "decision": "non_identity",
        "include": [{"service_token": {"token_id": "tok-1"}}],
        "exclude": [],
        "require": [],
    }
    assert owner == {
        "name": "orc-plane-owner",
        "decision": "allow",
        "include": [{"email": {"email": "owner@example.com"}}],
        "exclude": [],
        "require": [],
    }


def test_the_service_token_is_found_by_exact_name() -> None:
    tokens = [{"id": "other", "name": "orc-plane-tests-old"}, TOKEN]
    assert access.service_token_id(tokens) == "tok-1"


@pytest.mark.parametrize("tokens", [[], [{"id": "x", "name": "Orc-Plane-Tests"}], [TOKEN, {**TOKEN, "id": "tok-2"}]])
def test_a_missing_or_doubled_service_token_is_refused_naming_the_readme_step(tokens: list) -> None:
    with pytest.raises(Refusal) as caught:
        access.service_token_id(tokens)
    assert "orc-plane-tests" in str(caught.value)
    assert "step 3" in str(caught.value)


def test_the_one_time_pin_provider_is_found_by_type() -> None:
    assert access.one_time_pin_id([{"id": "gh", "type": "github"}, PIN]) == "pin-1"


@pytest.mark.parametrize("providers", [[], [{"id": "gh", "type": "github"}], [PIN, {**PIN, "id": "pin-2"}]])
def test_a_missing_or_doubled_one_time_pin_provider_is_refused(providers: list) -> None:
    with pytest.raises(Refusal) as caught:
        access.one_time_pin_id(providers)
    assert "step 2" in str(caught.value)


def test_a_policy_is_found_by_exact_name() -> None:
    policies = [{"id": "p0", "name": "orc-plane-owner-old"}, {"id": "p1", "name": "orc-plane-owner"}]
    assert access.one_named(policies, "orc-plane-owner", "reusable Access policy") == {
        "id": "p1",
        "name": "orc-plane-owner",
    }
    assert access.one_named(policies, "orc-plane-service-token", "reusable Access policy") is None


def test_two_policies_with_one_name_are_refused_naming_it_and_the_runbook() -> None:
    policies = [{"id": "p1", "name": "orc-plane-owner"}, {"id": "p2", "name": "orc-plane-owner"}]
    with pytest.raises(Refusal) as caught:
        access.one_named(policies, "orc-plane-owner", "reusable Access policy")
    assert "orc-plane-owner" in str(caught.value)
    assert "docs/cleanup.md" in str(caught.value)


def test_a_policy_matches_when_decision_and_rules_are_the_same() -> None:
    service, owner = access.desired_policies("tok-1", "Owner@Example.com")
    observed_owner = {
        "id": "p",
        "name": "orc-plane-owner",
        "decision": "allow",
        "include": [{"email": {"email": "owner@example.com"}}],
        "exclude": [],
        "require": [],
        "created_at": "2026-10-23T00:00:00Z",
    }
    assert access.policy_matches(observed_owner, owner)
    observed_service = {"name": "orc-plane-service-token", "decision": "non_identity", **_rules(service)}
    del observed_service["exclude"]
    assert access.policy_matches(observed_service, service)


def _rules(policy: dict) -> dict:
    return {"include": policy["include"], "exclude": policy["exclude"], "require": policy["require"]}


@pytest.mark.parametrize(
    "change",
    [
        {"decision": "allow"},
        {"include": [{"service_token": {"token_id": "rotated"}}]},
        {"include": [{"service_token": {"token_id": "tok-1"}}, {"everyone": {}}]},
        {"exclude": [{"everyone": {}}]},
        {"require": [{"everyone": {}}]},
    ],
)
def test_a_policy_that_differs_does_not_match(change: dict) -> None:
    service, _ = access.desired_policies("tok-1", "owner@example.com")
    assert not access.policy_matches({**service, **change}, service)


def test_apps_are_found_by_their_worker_destination() -> None:
    apps = [
        {"id": "a1", "name": "x", "destinations": [{"type": "worker", "worker_id": "w1"}]},
        {"id": "a2", "name": "y", "destinations": [{"type": "public", "uri": "y.example.com"}]},
        {"id": "a3", "name": "z", "destinations": [{"type": "worker", "worker_id": "tag-1"}]},
        {"id": "a4", "name": "q"},
    ]
    assert [app["id"] for app in access.apps_for_worker(apps, frozenset({"w1", "tag-1"}))] == ["a1", "a3"]
    assert access.apps_for_worker(apps, frozenset()) == []


def _desired_app() -> dict:
    return static_site.access_application("example-site-dev", "w1", ("svc", "own"), "pin-1")


def test_an_app_matches_when_every_field_the_plane_sets_is_the_same() -> None:
    observed = {
        "id": "a1",
        "aud": "x",
        "domain": "example-site-dev.acme.workers.dev",
        **_desired_app(),
        "policies": [
            {"id": "own", "precedence": 2, "name": "orc-plane-owner", "decision": "allow"},
            {"id": "svc", "precedence": 1, "name": "orc-plane-service-token", "decision": "non_identity"},
        ],
        "destinations": [{"type": "worker", "worker_id": "w1"}],
    }
    assert access.app_matches(observed, _desired_app(), frozenset({"w1"}))


def test_an_app_without_the_optional_flags_in_its_response_still_matches() -> None:
    observed = {**_desired_app()}
    del observed["app_launcher_visible"]
    del observed["auto_redirect_to_identity"]
    assert access.app_matches(observed, _desired_app(), frozenset({"w1"}))


@pytest.mark.parametrize(
    "change",
    [
        {"name": "renamed"},
        {"type": "warp"},
        {"destinations": [{"type": "worker", "worker_id": "w1"}, {"type": "public", "uri": "x.example.com"}]},
        {"destinations": [{"type": "worker", "worker_id": "other"}]},
        {"policies": [{"id": "svc", "precedence": 1}]},
        {"policies": [{"id": "own", "precedence": 1}, {"id": "svc", "precedence": 2}]},
        {"allowed_idps": []},
        {"allowed_idps": ["pin-1", "github"]},
        {"auto_redirect_to_identity": False},
        {"app_launcher_visible": True},
    ],
)
def test_an_app_that_differs_does_not_match(change: dict) -> None:
    assert not access.app_matches({**_desired_app(), **change}, _desired_app(), frozenset({"w1"}))
