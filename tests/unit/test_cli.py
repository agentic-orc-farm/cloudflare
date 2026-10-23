import json
from pathlib import Path

import pytest
from tests.helpers import COMMIT, ORG, PROJECT, environment_without_credentials

from cf_plane.cli import COMMANDS, Services, main

SITE = {"name": "site", "kind": "static-site", "plane": "cloudflare", "artefact": "site"}


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID", "GITHUB_READ_TOKEN", "ACCESS_OWNER_EMAIL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PLANE_ORG", ORG)


def inputs_arguments(command: str, result: Path, **overrides: str) -> list[str]:
    values = {
        "project": PROJECT,
        "commit": COMMIT,
        "env": "prod",
        "mode": "plan",
        "components": json.dumps([SITE]),
        **overrides,
    }
    arguments = [command]
    for name, value in values.items():
        arguments += [f"--{name}", value]
    return [*arguments, "--result", str(result)]


def test_the_command_runs_with_no_arguments() -> None:
    assert main([]) == 0


def test_the_command_surface_is_validate_deploy_and_wrangler_config() -> None:
    assert [command.name for command in COMMANDS] == ["validate", "deploy", "wrangler-config"]


def test_command_names_are_unique() -> None:
    names = [command.name for command in COMMANDS]
    assert len(names) == len(set(names))


def test_wrangler_config_prints_the_translation(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    code = main(
        [
            "wrangler-config",
            "--project",
            PROJECT,
            "--env",
            "dev",
            "--component",
            json.dumps(SITE),
            "--assets",
            str(tmp_path),
        ]
    )
    assert code == 0
    config = json.loads(capsys.readouterr().out)
    assert config["name"] == "example-site-dev"
    assert config["assets"]["directory"] == str(tmp_path)


def test_wrangler_config_refuses_an_unknown_kind_on_stderr(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    component = json.dumps({**SITE, "kind": "queue"})
    code = main(["wrangler-config", "--project", PROJECT, "--env", "dev", "--component", component, "--assets", "x"])
    assert code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "queue" in captured.err


def test_wrangler_config_refuses_a_worker_name_over_63_characters(capsys: pytest.CaptureFixture) -> None:
    project = f"{ORG}/{'r' * 60}"
    code = main(
        ["wrangler-config", "--project", project, "--env", "dev", "--component", json.dumps(SITE), "--assets", "x"]
    )
    assert code == 1
    assert "63" in capsys.readouterr().err


def test_validate_prints_the_repository_name_and_writes_nothing(
    offline: None, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    result = tmp_path / "result.json"
    assert main(inputs_arguments("validate", result)) == 0
    assert capsys.readouterr().out == "example\n"
    assert not result.exists()


def test_validate_refusal_writes_result_json_and_says_why_on_stderr(
    offline: None, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    result = tmp_path / "result.json"
    assert main(inputs_arguments("validate", result, commit="abc")) == 1
    written = json.loads(result.read_text())
    assert written["components"] == []
    assert written["summary"].startswith("commit:")
    assert "commit:" in capsys.readouterr().err


def test_deploy_without_credentials_fails_after_validation_naming_them(offline: None, tmp_path: Path) -> None:
    result = tmp_path / "result.json"
    assert main(inputs_arguments("deploy", result)) == 1
    written = json.loads(result.read_text())
    assert set(written) == {"schema_version", "components", "summary"}
    assert written["components"] == []
    assert "CLOUDFLARE_API_TOKEN" in written["summary"]
    assert "ACCESS_OWNER_EMAIL" not in written["summary"]


def test_deploy_to_dev_without_the_owner_email_is_refused_before_credentials(offline: None, tmp_path: Path) -> None:
    result = tmp_path / "result.json"
    assert main(inputs_arguments("deploy", result, env="dev")) == 1
    written = json.loads(result.read_text())
    assert "ACCESS_OWNER_EMAIL" in written["summary"]
    assert "CLOUDFLARE_API_TOKEN" not in written["summary"]


def test_a_result_path_in_a_missing_folder_is_refused(offline: None, tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="does not exist"):
        main(inputs_arguments("validate", tmp_path / "absent" / "result.json", commit="abc"))


def test_services_from_the_environment_keep_the_other_secrets_from_wrangler() -> None:
    environment = {
        **environment_without_credentials(),
        "CLOUDFLARE_API_TOKEN": "t",
        "CLOUDFLARE_ACCOUNT_ID": "a",
        "GITHUB_READ_TOKEN": "g",
        "ACCESS_OWNER_EMAIL": "o@example.com",
        "CF_ACCESS_CLIENT_SECRET": "s",
    }
    services = Services.from_environment(environment)
    assert services.wrangler_environment["CLOUDFLARE_API_TOKEN"] == "t"
    for name in ("GITHUB_READ_TOKEN", "ACCESS_OWNER_EMAIL", "CF_ACCESS_CLIENT_SECRET"):
        assert name not in services.wrangler_environment
    assert services.wrangler.parts[-3:] == ("node_modules", ".bin", "wrangler")


def test_httpx_request_logs_are_silenced_because_their_urls_hold_the_account_id(tmp_path: Path) -> None:
    import logging

    logging.getLogger("httpx").setLevel(logging.NOTSET)
    main(["wrangler-config", "--project", PROJECT, "--env", "dev", "--component", json.dumps(SITE), "--assets", "x"])
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
