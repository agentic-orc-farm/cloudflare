import zipfile
from pathlib import Path

import httpx
import pytest
from tests.helpers import COMMIT, PROJECT, READ_TOKEN, FakeGitHub, zip_bytes

from cf_plane.artefacts import ArtefactError, GitHubArtefacts, unpack


def github(fake: FakeGitHub) -> GitHubArtefacts:
    return GitHubArtefacts(READ_TOKEN, transport=fake.transport())


def test_the_newest_unexpired_artefact_of_the_projects_own_run_for_the_commit_is_found() -> None:
    fake = FakeGitHub(page_size=2)
    fake.add("site", {}, commit="b" * 40)
    fake.add("site", {}, created_at="2026-10-23T09:00:00Z")
    newest = fake.add("site", {}, created_at="2026-10-23T11:00:00Z")
    fake.add("site", {}, created_at="2026-10-23T12:00:00Z", expired=True)
    fake.add("site", {}, created_at="2026-10-23T13:00:00Z", fork=True)
    fake.add("other", {}, created_at="2026-10-23T14:00:00Z")
    fake.add("site", {}, created_at="2026-10-23T15:00:00Z", project="agentic-orc-farm/else")
    assert github(fake).find(PROJECT, "site", COMMIT).id == newest


@pytest.mark.parametrize("variant", ["none", "expired", "fork", "other-commit"])
def test_no_usable_artefact_is_refused_naming_it_the_commit_and_the_retention(variant: str) -> None:
    fake = FakeGitHub()
    if variant != "none":
        fake.add(
            "site",
            {},
            expired=variant == "expired",
            fork=variant == "fork",
            commit="b" * 40 if variant == "other-commit" else COMMIT,
        )
    with pytest.raises(ArtefactError) as caught:
        github(fake).find(PROJECT, "site", COMMIT)
    message = str(caught.value)
    assert "site" in message
    assert COMMIT in message
    assert "90 days" in message


def test_the_download_follows_the_storage_redirect_without_the_token(tmp_path: Path) -> None:
    fake = FakeGitHub()
    fake.add("site", {"index.html": "<h1>hi</h1>"})
    client = github(fake)
    artefact = client.find(PROJECT, "site", COMMIT)
    archive = client.download(PROJECT, artefact, tmp_path / "site.zip")
    assert zipfile.ZipFile(archive).read("index.html") == b"<h1>hi</h1>"
    assert fake.storage_headers
    assert all("authorization" not in headers for headers in fake.storage_headers)


def test_a_failed_listing_is_an_artefact_error_without_the_token() -> None:
    def deny(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Bad credentials"})

    with pytest.raises(ArtefactError) as caught:
        GitHubArtefacts(READ_TOKEN, transport=httpx.MockTransport(deny)).find(PROJECT, "site", COMMIT)
    assert "401" in str(caught.value)
    assert READ_TOKEN not in str(caught.value)


def test_unpack_writes_the_files_into_the_folder(tmp_path: Path) -> None:
    archive = tmp_path / "a.zip"
    archive.write_bytes(zip_bytes({"index.html": "home", "docs/404.html": "missing"}))
    unpack(archive, tmp_path / "out")
    assert (tmp_path / "out" / "index.html").read_text() == "home"
    assert (tmp_path / "out" / "docs" / "404.html").read_text() == "missing"


@pytest.mark.parametrize(
    ("files", "symlinks", "rule"),
    [
        ({"/etc/passwd": "x"}, None, "absolute"),
        ({"../escape.txt": "x"}, None, ".."),
        ({"a/../../escape.txt": "x"}, None, ".."),
        ({"C:\\windows.txt": "x"}, None, "absolute"),
        ({}, {"link": "/etc/passwd"}, "symlink"),
    ],
)
def test_unsafe_entries_are_refused_naming_the_rule(
    tmp_path: Path, files: dict, symlinks: dict | None, rule: str
) -> None:
    archive = tmp_path / "a.zip"
    archive.write_bytes(zip_bytes(files, symlinks=symlinks))
    with pytest.raises(ArtefactError) as caught:
        unpack(archive, tmp_path / "out")
    assert rule in str(caught.value)
    assert not (tmp_path / "escape.txt").exists()


def test_too_many_files_are_refused(tmp_path: Path) -> None:
    archive = tmp_path / "a.zip"
    archive.write_bytes(zip_bytes({f"f{i}.txt": "x" for i in range(4)}))
    with pytest.raises(ArtefactError, match="files"):
        unpack(archive, tmp_path / "out", max_files=3)


def test_too_many_bytes_unpacked_are_refused(tmp_path: Path) -> None:
    archive = tmp_path / "a.zip"
    archive.write_bytes(zip_bytes({"big.txt": "x" * 2000}))
    with pytest.raises(ArtefactError, match="MB|bytes"):
        unpack(archive, tmp_path / "out", max_bytes=1000)


def test_a_file_that_is_not_a_zip_is_refused(tmp_path: Path) -> None:
    archive = tmp_path / "a.zip"
    archive.write_bytes(b"not a zip")
    with pytest.raises(ArtefactError, match="zip"):
        unpack(archive, tmp_path / "out")
