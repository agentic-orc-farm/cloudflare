from pathlib import Path

import pytest

from cf_plane import static_site
from cf_plane.contract import Refusal

COMMIT = "4f2b9c0d1e3a5b7c9d0e2f4a6b8c0d2e4f6a8b0c"


def test_worker_name_joins_repo_component_and_env() -> None:
    assert static_site.worker_name("example", "site", "prod") == "example-site-prod"


def test_worker_name_of_exactly_63_characters_is_allowed() -> None:
    repo = "r" * (63 - len("-site-prod"))
    assert len(static_site.worker_name(repo, "site", "prod")) == 63


def test_worker_name_over_63_characters_is_refused_naming_it_and_63() -> None:
    repo = "r" * (64 - len("-site-prod"))
    with pytest.raises(Refusal) as caught:
        static_site.worker_name(repo, "site", "prod")
    message = str(caught.value)
    assert f"{repo}-site-prod" in message
    assert "63" in message
    assert message.startswith("components:")


def test_url_is_on_the_account_workers_dev_subdomain() -> None:
    assert static_site.url("example-site-dev", "acme") == "https://example-site-dev.acme.workers.dev"


def test_wrangler_config_serves_assets_only_with_previews_off(tmp_path: Path) -> None:
    config = static_site.wrangler_config("example-site-prod", tmp_path)
    assert config == {
        "name": "example-site-prod",
        "compatibility_date": static_site.COMPATIBILITY_DATE,
        "workers_dev": True,
        "preview_urls": False,
        "assets": {"directory": str(tmp_path), "not_found_handling": "404-page"},
    }


def test_first_deploy_of_a_private_worker_can_turn_workers_dev_off(tmp_path: Path) -> None:
    config = static_site.wrangler_config("example-site-dev", tmp_path, workers_dev=False)
    assert config["workers_dev"] is False
    assert config["preview_urls"] is False


def test_config_hash_ignores_the_assets_folder_and_workers_dev(tmp_path: Path) -> None:
    one = static_site.config_hash(static_site.wrangler_config("w", tmp_path / "a"))
    two = static_site.config_hash(static_site.wrangler_config("w", tmp_path / "b", workers_dev=False))
    assert one == two
    assert len(one) == 12
    assert int(one, 16) >= 0


def test_config_hash_changes_with_the_configuration(tmp_path: Path) -> None:
    one = static_site.config_hash(static_site.wrangler_config("w", tmp_path))
    two = static_site.config_hash(static_site.wrangler_config("v", tmp_path))
    assert one != two


def test_marker_round_trips() -> None:
    text = static_site.marker("agentic-orc-farm/example", COMMIT, "0123456789ab")
    assert text == f"orc project=agentic-orc-farm/example commit={COMMIT} config=0123456789ab"
    parsed = static_site.parse_marker(text)
    assert parsed == static_site.Marker("agentic-orc-farm/example", COMMIT, "0123456789ab")


@pytest.mark.parametrize(
    "text",
    [None, "", "deployed by hand", "orc project=x", f"orc project=a/b commit={COMMIT} config=0123456789ab extra"],
)
def test_text_that_is_not_a_marker_parses_as_none(text: str | None) -> None:
    assert static_site.parse_marker(text) is None


def test_desired_marker_is_built_from_the_project_commit_and_configuration() -> None:
    desired = static_site.desired_marker("agentic-orc-farm/example", COMMIT, "example-site-prod")
    parsed = static_site.parse_marker(desired)
    assert parsed is not None
    assert parsed.project == "agentic-orc-farm/example"
    assert parsed.commit == COMMIT
    assert parsed.config == static_site.config_hash(static_site.wrangler_config("example-site-prod", Path("x")))


def test_access_application_protects_the_worker_with_the_two_policies() -> None:
    app = static_site.access_application("example-site-dev", "wid", ("svc", "own"), "pin")
    assert app == {
        "type": "self_hosted",
        "name": "example-site-dev",
        "destinations": [{"type": "worker", "worker_id": "wid"}],
        "policies": [{"id": "svc", "precedence": 1}, {"id": "own", "precedence": 2}],
        "allowed_idps": ["pin"],
        "auto_redirect_to_identity": True,
        "app_launcher_visible": False,
    }
