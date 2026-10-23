import json
import logging
import stat
from pathlib import Path

import pytest
from tests.helpers import ACCOUNT, TOKEN, read_wrangler_log, write_fake_wrangler

from cf_plane.wrangler import WranglerError, deploy

CONFIG = {
    "name": "example-site-prod",
    "workers_dev": True,
    "preview_urls": False,
    "assets": {"directory": "", "not_found_handling": "404-page"},
}


def config_for(assets: Path) -> dict:
    return {**CONFIG, "assets": {**CONFIG["assets"], "directory": str(assets)}}


@pytest.fixture
def assets(tmp_path: Path) -> Path:
    folder = tmp_path / "assets"
    folder.mkdir()
    (folder / "index.html").write_text("home")
    return folder


def environment(log: Path, **extra: str) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "CLOUDFLARE_API_TOKEN": TOKEN,
        "CLOUDFLARE_ACCOUNT_ID": ACCOUNT,
        "FAKE_WRANGLER_LOG": str(log),
        **extra,
    }


def test_deploy_writes_the_configuration_and_passes_the_marker(tmp_path: Path, assets: Path) -> None:
    wrangler = write_fake_wrangler(tmp_path)
    log = tmp_path / "log.jsonl"
    deploy(
        config_for(assets), "orc marker", wrangler=wrangler, work_dir=tmp_path / "work", environment=environment(log)
    )
    [record] = read_wrangler_log(log)
    assert record["config"] == config_for(assets)
    assert record["message"] == "orc marker"
    assert record["arguments"][0] == "deploy"
    assert record["files"] == {"index.html": "home"}
    assert record["metrics"] == "false"
    assert json.loads((tmp_path / "work" / "wrangler.json").read_text()) == config_for(assets)


def test_a_failed_deploy_names_the_worker_and_keeps_secrets_out_of_the_log(
    tmp_path: Path, assets: Path, caplog: pytest.LogCaptureFixture
) -> None:
    wrangler = write_fake_wrangler(tmp_path)
    caplog.set_level(logging.INFO)
    with pytest.raises(WranglerError) as caught:
        deploy(
            config_for(assets),
            "orc marker",
            wrangler=wrangler,
            work_dir=tmp_path / "work",
            environment=environment(tmp_path / "log.jsonl", FAKE_WRANGLER_EXIT="3"),
        )
    assert "example-site-prod" in str(caught.value)
    assert "3" in str(caught.value)
    assert "deploy failed" in caplog.text
    assert ACCOUNT not in caplog.text
    assert TOKEN not in caplog.text


def test_a_wrangler_that_hangs_is_killed_with_its_process_group(tmp_path: Path, assets: Path) -> None:
    hanging = tmp_path / "hanging"
    hanging.write_text("#!/bin/sh\nsleep 30 &\nsleep 30\n")
    hanging.chmod(hanging.stat().st_mode | stat.S_IXUSR)
    with pytest.raises(WranglerError, match="did not finish"):
        deploy(
            config_for(assets),
            "m",
            wrangler=hanging,
            work_dir=tmp_path / "work",
            environment=environment(tmp_path / "log"),
            timeout=0.5,
        )


def test_a_missing_wrangler_says_to_run_make_setup(tmp_path: Path, assets: Path) -> None:
    with pytest.raises(WranglerError, match="make setup"):
        deploy(
            config_for(assets),
            "m",
            wrangler=tmp_path / "absent",
            work_dir=tmp_path / "work",
            environment=environment(tmp_path / "log"),
        )
