"""Write wrangler.json and run node_modules/.bin/wrangler."""

import json
import logging
import os
import signal
import subprocess
from collections.abc import Mapping
from pathlib import Path

from cf_plane.contract import PlaneError

TIMEOUT_SECONDS = 300.0
DEFAULT_WRANGLER = Path("node_modules/.bin/wrangler")
# The values wrangler's output could echo (an API path holds the account id); masked before anything is logged.
_SECRET_VARIABLES = ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID")

logger = logging.getLogger(__name__)


class WranglerError(PlaneError):
    """wrangler could not be run, failed or did not finish."""


def deploy(
    config: dict,
    message: str,
    *,
    wrangler: Path,
    work_dir: Path,
    environment: Mapping[str, str],
    timeout: float = TIMEOUT_SECONDS,
) -> None:
    """Deploy one Worker: write its configuration and run `wrangler deploy` with the marker as its message."""
    work_dir.mkdir(parents=True, exist_ok=True)
    config_path = work_dir / "wrangler.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    command = [str(wrangler), "deploy", "--config", str(config_path), "--message", message]
    secrets = [environment[name] for name in _SECRET_VARIABLES if environment.get(name)]
    output, exit_code = _run(command, {**environment, "WRANGLER_SEND_METRICS": "false"}, work_dir, timeout)
    for line in _masked(output, secrets).splitlines():
        logger.info("wrangler: %s", line)
    if exit_code != 0:
        raise WranglerError(f"wrangler deploy of {config['name']} exited {exit_code}; its output is in the run log.")


def _run(command: list[str], environment: Mapping[str, str], cwd: Path, timeout: float) -> tuple[str, int]:
    """Run COMMAND in its own process group, killing the whole group if it outlives TIMEOUT."""
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=dict(environment),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
    except OSError as error:
        raise WranglerError(
            f"wrangler could not be started ({type(error).__name__}); run `make setup` to install the pinned wrangler."
        ) from None
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise WranglerError(f"wrangler did not finish within {timeout:g} seconds and was stopped.") from None
    return output, process.returncode


def _masked(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        text = text.replace(secret, "***")
    return text
