"""Fixtures for the unit tests. The helpers they use live in tests/helpers.py."""

from pathlib import Path

import pytest
from tests.helpers import ACCOUNT, READ_TOKEN, TOKEN, FakeCloudflare, FakeGitHub, write_fake_wrangler

from cf_plane.artefacts import GitHubArtefacts
from cf_plane.cli import Services
from cf_plane.cloudflare import Cloudflare


class World:
    """A fake Cloudflare account, a fake GitHub, a fake wrangler, and the services a deploy uses over them."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.wrangler_log = folder / "wrangler.jsonl"
        self.cloudflare = FakeCloudflare(wrangler_log=self.wrangler_log)
        self.github = FakeGitHub()
        self.sleeps: list[float] = []
        self.wrangler_environment = {
            "PATH": "/usr/bin:/bin",
            "CLOUDFLARE_API_TOKEN": TOKEN,
            "CLOUDFLARE_ACCOUNT_ID": ACCOUNT,
            "FAKE_WRANGLER_LOG": str(self.wrangler_log),
        }
        self.wrangler = write_fake_wrangler(folder)
        self.read_token: str | None = READ_TOKEN
        self.runs = 0

    def services(self) -> Services:
        def github() -> GitHubArtefacts:
            if self.read_token is None:
                raise AssertionError("the run asked for the read token")
            return GitHubArtefacts(self.read_token, transport=self.github.transport())

        return Services(
            cloudflare=Cloudflare(TOKEN, ACCOUNT, transport=self.cloudflare.transport()),
            github=github,
            wrangler=self.wrangler,
            wrangler_environment=self.wrangler_environment,
            sleep=self._sleep,
        )

    def _sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.cloudflare.effects.append(f"wait {seconds:g}")

    def scratch(self) -> Path:
        self.runs += 1
        folder = self.folder / f"scratch-{self.runs}"
        folder.mkdir()
        return folder


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path)
