"""AC5 and AC31: `cf-plane wrangler-config`, the credential-free view of the static-site translation. Offline."""

import json
from pathlib import Path

import pytest
from tests.acceptance.helpers import EXAMPLE_PROJECT, component, offline_environment, run_cf_plane


def _wrangler_config(env: str, assets: Path) -> dict:
    run = run_cf_plane(
        [
            "wrangler-config",
            "--project",
            EXAMPLE_PROJECT,
            "--env",
            env,
            "--component",
            json.dumps(component("site")),
            "--assets",
            str(assets),
        ],
        offline_environment(),
    )
    assert run.exit_code == 0, run.describe()
    try:
        config = json.loads(run.stdout)
    except json.JSONDecodeError as error:
        pytest.fail(f"cf-plane wrangler-config did not print JSON ({error}):\n{run.describe()}")
    assert isinstance(config, dict), f"printed {config!r}, not a JSON object"
    return config


def _check(config: dict, name: str, assets: Path) -> None:
    assert config.get("name") == name
    assert config.get("workers_dev") is True
    assert config.get("preview_urls") is False
    assert "main" not in config, "a static site has no `main`: the artefact is served as it is"
    asset_settings = config.get("assets")
    assert isinstance(asset_settings, dict), f"assets is {asset_settings!r}"
    directory = asset_settings.get("directory")
    assert isinstance(directory, str), f"assets.directory is {directory!r}"
    assert Path(directory).resolve() == assets.resolve()
    assert asset_settings.get("not_found_handling") == "404-page"


def test_AC5_prod_configuration_for_a_static_site(tmp_path: Path) -> None:
    assets = tmp_path / "unpacked-artefact"
    assets.mkdir()
    _check(_wrangler_config("prod", assets), "example-site-prod", assets)


def test_AC31_staging_configuration_for_a_static_site(tmp_path: Path) -> None:
    assets = tmp_path / "unpacked-artefact"
    assets.mkdir()
    _check(_wrangler_config("staging", assets), "example-site-staging", assets)
