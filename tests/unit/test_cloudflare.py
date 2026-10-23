import httpx
import pytest
from tests.helpers import ACCOUNT, TOKEN, FakeCloudflare

from cf_plane.cloudflare import Cloudflare, CloudflareError

MARKER = "orc project=agentic-orc-farm/example commit=" + "a" * 40 + " config=0123456789ab"


def client(fake: FakeCloudflare) -> Cloudflare:
    return Cloudflare(TOKEN, ACCOUNT, transport=fake.transport())


def test_the_workers_subdomain_is_read() -> None:
    assert client(FakeCloudflare(subdomain="acme")).workers_subdomain() == "acme"


def test_an_absent_worker_is_observed_as_absent() -> None:
    observed = client(FakeCloudflare()).observe_workers(["example-site-prod"])
    assert observed["example-site-prod"].exists is False


def test_an_existing_worker_is_observed_with_ids_deployments_and_subdomain_settings() -> None:
    fake = FakeCloudflare()
    fake.add_script("example-site-prod", None)
    fake.add_script("example-site-prod", MARKER, workers_dev=True, previews=False)
    observed = client(fake).observe_workers(["example-site-prod"])["example-site-prod"]
    assert observed.exists
    assert observed.worker_id == "wid-example-site-prod"
    assert observed.ids == frozenset({"wid-example-site-prod", "tag-example-site-prod"})
    assert observed.active_message == MARKER
    assert observed.owner == "agentic-orc-farm/example"
    assert (observed.workers_dev, observed.previews) == (True, False)


def test_without_deployment_annotations_the_message_is_read_from_the_version() -> None:
    fake = FakeCloudflare(deployment_annotations=False)
    fake.add_script("example-site-prod", MARKER)
    observed = client(fake).observe_workers(["example-site-prod"])["example-site-prod"]
    assert observed.active_message == MARKER


def test_without_the_workers_api_the_script_tag_is_the_worker_id() -> None:
    fake = FakeCloudflare(workers_api=False)
    fake.add_script("example-site-dev", MARKER)
    observed = client(fake).observe_workers(["example-site-dev"])["example-site-dev"]
    assert observed.worker_id == "tag-example-site-dev"


def test_access_objects_are_read_across_every_page() -> None:
    fake = FakeCloudflare(page_size=2)
    fake.policies = [{"id": f"p{i}", "name": f"policy-{i}"} for i in range(5)]
    fake.apps = [{"id": "a1", "name": "x"}]
    observed = client(fake).observe_access()
    assert [policy["id"] for policy in observed.policies] == ["p0", "p1", "p2", "p3", "p4"]
    assert [app["id"] for app in observed.apps] == ["a1"]
    assert [token["name"] for token in observed.service_tokens] == ["orc-plane-tests"]
    assert {provider["type"] for provider in observed.identity_providers} == {"github", "onetimepin"}


def test_policies_and_apps_are_created_and_updated_in_place() -> None:
    fake = FakeCloudflare()
    cloudflare = client(fake)
    policy_id = cloudflare.create_policy({"name": "orc-plane-owner", "decision": "allow", "include": []})
    cloudflare.update_policy(policy_id, {"name": "orc-plane-owner", "decision": "deny", "include": []})
    assert fake.policies == [{"id": policy_id, "name": "orc-plane-owner", "decision": "deny", "include": []}]
    app_id = cloudflare.create_app({"name": "w", "policies": [{"id": policy_id, "precedence": 1}]})
    cloudflare.update_app(app_id, {"name": "w2", "policies": []})
    assert [(app["id"], app["name"]) for app in fake.apps] == [(app_id, "w2")]


def test_workers_dev_is_turned_on_with_previews_off() -> None:
    fake = FakeCloudflare()
    fake.add_script("example-site-dev", MARKER, workers_dev=False, previews=True)
    client(fake).enable_workers_dev("example-site-dev")
    script = fake.scripts["example-site-dev"]
    assert (script.workers_dev, script.previews) == (True, False)


def test_an_error_names_the_call_and_status_but_not_the_account_or_access_messages() -> None:
    fake = FakeCloudflare(fail={("GET", "/access/apps"): 403})
    with pytest.raises(CloudflareError) as caught:
        client(fake).observe_access()
    message = str(caught.value)
    assert "GET /access/apps" in message
    assert "403" in message
    assert ACCOUNT not in message
    assert "injected failure" not in message


def test_a_workers_error_carries_cloudflares_message() -> None:
    fake = FakeCloudflare(fail={("GET", "/workers/subdomain"): 403})
    with pytest.raises(CloudflareError, match="injected failure"):
        client(fake).workers_subdomain()


def test_a_network_failure_is_a_cloudflare_error_without_the_url() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    cloudflare = Cloudflare(TOKEN, ACCOUNT, transport=httpx.MockTransport(refuse))
    with pytest.raises(CloudflareError) as caught:
        cloudflare.workers_subdomain()
    assert "ConnectTimeout" in str(caught.value)
    assert ACCOUNT not in str(caught.value)


def test_every_request_has_a_30_second_timeout() -> None:
    seen: list[dict] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request.extensions["timeout"])
        return httpx.Response(200, json={"success": True, "result": {"subdomain": "acme"}})

    Cloudflare(TOKEN, ACCOUNT, transport=httpx.MockTransport(record)).workers_subdomain()
    assert seen == [{"connect": 30.0, "read": 30.0, "write": 30.0, "pool": 30.0}]
