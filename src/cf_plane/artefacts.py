"""Find, download and safely unpack a project's artefact."""

import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

import httpx

from cf_plane.contract import PlaneError

API = "https://api.github.com"
TIMEOUT_SECONDS = 30.0
DOWNLOAD_TIMEOUT_SECONDS = 120.0
# 20,000 is the Workers Free plan's asset file limit; wrangler itself refuses a single file over 25 MiB.
MAX_FILES = 20_000
MAX_BYTES = 500 * 1024 * 1024
_PER_PAGE = 100
_CHUNK = 1024 * 1024


class ArtefactError(PlaneError):
    """An artefact could not be found, downloaded or safely unpacked."""


@dataclass(frozen=True)
class Artefact:
    """One artefact of a project's workflow run."""

    id: int
    name: str
    created_at: str


class GitHubArtefacts:
    """Reads a project's Actions artefacts with a read-only token scoped to that one repository."""

    def __init__(
        self,
        token: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = TIMEOUT_SECONDS,
        download_timeout: float = DOWNLOAD_TIMEOUT_SECONDS,
    ) -> None:
        self._transport = transport
        self._download_timeout = download_timeout
        self._client = httpx.Client(
            base_url=API,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
        )

    def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        try:
            response = self._client.get(path, params=params)
        except httpx.HTTPError as error:
            raise ArtefactError(f"GET {path} failed: {type(error).__name__}; run the workflow again.") from None
        if response.status_code >= 400:
            raise ArtefactError(f"GET {path} returned {response.status_code}; check the plane's reader App.")
        return response

    def find(self, project: str, name: str, commit: str) -> Artefact:
        """The newest unexpired artefact NAME from a run of the project itself (not a fork) for COMMIT."""
        candidates = [
            item
            for item in self._list(project, name)
            if item.get("name") == name
            and not item.get("expired")
            and (run := item.get("workflow_run") or {}).get("head_sha") == commit
            and run.get("repository_id") is not None
            and run.get("head_repository_id") == run.get("repository_id")
        ]
        if not candidates:
            raise ArtefactError(
                f"no artefact named {name} for commit {commit} in {project}: the project's CI must upload it "
                "for that commit, and artefacts expire with the project's retention setting (90 days by default)."
            )
        newest = max(candidates, key=lambda item: str(item.get("created_at") or ""))
        return Artefact(id=int(newest["id"]), name=name, created_at=str(newest.get("created_at") or ""))

    def _list(self, project: str, name: str) -> list[dict]:
        found: list[dict] = []
        page = 1
        while True:
            body = self._get(
                f"/repos/{project}/actions/artifacts", params={"name": name, "per_page": _PER_PAGE, "page": page}
            ).json()
            batch = body.get("artifacts") or []
            found.extend(batch)
            if not batch or len(found) >= int(body.get("total_count") or 0):
                return found
            page += 1

    def download(self, project: str, artefact: Artefact, destination: Path) -> Path:
        """Download the artefact's zip to DESTINATION; the token is not sent to the storage it redirects to."""
        path = f"/repos/{project}/actions/artifacts/{artefact.id}/zip"
        response = self._get(path)
        if response.is_redirect:
            location = response.headers.get("location")
            if not location:
                raise ArtefactError(f"GET {path} redirected nowhere; run the workflow again.")
            self._fetch_storage(location, destination, artefact)
        else:
            destination.write_bytes(response.content)
        return destination

    def _fetch_storage(self, location: str, destination: Path, artefact: Artefact) -> None:
        # A fresh client with no headers: the Authorization header never crosses to the storage host.
        try:
            with (
                httpx.Client(timeout=self._download_timeout, transport=self._transport) as storage,
                storage.stream("GET", location) as response,
            ):
                if response.status_code >= 400:
                    raise ArtefactError(f"downloading artefact {artefact.name} returned {response.status_code}.")
                written = 0
                with destination.open("wb") as file:
                    for chunk in response.iter_bytes(_CHUNK):
                        written += len(chunk)
                        if written > MAX_BYTES:
                            raise ArtefactError(f"artefact {artefact.name} is larger than {MAX_BYTES // 2**20} MB.")
                        file.write(chunk)
        except httpx.HTTPError as error:
            raise ArtefactError(f"downloading artefact {artefact.name} failed: {type(error).__name__}.") from None


def unpack(archive: Path, folder: Path, *, max_files: int = MAX_FILES, max_bytes: int = MAX_BYTES) -> Path:
    """Unpack ARCHIVE into the new FOLDER, refusing anything that could escape it or exhaust the runner."""
    try:
        with zipfile.ZipFile(archive) as opened:
            members = [info for info in opened.infolist() if not info.is_dir()]
            _check_members(members, max_files, max_bytes)
            folder.mkdir()
            written = 0
            for info in members:
                written = _extract(opened, info, folder, written, max_bytes)
    except zipfile.BadZipFile:
        raise ArtefactError(f"the artefact {archive.name} is not a valid zip file.") from None
    return folder


def _check_members(members: list[zipfile.ZipInfo], max_files: int, max_bytes: int) -> None:
    if len(members) > max_files:
        raise ArtefactError(f"the artefact has {len(members)} files; the plane unpacks at most {max_files} files.")
    for info in members:
        name = info.filename
        if name.startswith(("/", "\\")) or PureWindowsPath(name).drive:
            raise ArtefactError(f"the artefact holds an absolute path ({name[:80]}); refused.")
        if ".." in PurePosixPath(name.replace("\\", "/")).parts:
            raise ArtefactError(f"the artefact holds a path with .. ({name[:80]}); refused.")
        if stat.S_ISLNK(info.external_attr >> 16):
            raise ArtefactError(f"the artefact holds a symlink ({name[:80]}); refused.")
    total = sum(info.file_size for info in members)
    if total > max_bytes:
        raise ArtefactError(
            f"the artefact unpacks to {total} bytes; the plane unpacks at most {max_bytes // 2**20} MB "
            f"({max_bytes} bytes)."
        )


def _extract(opened: zipfile.ZipFile, info: zipfile.ZipInfo, folder: Path, written: int, max_bytes: int) -> int:
    """Write one member, counting the bytes actually written, since a zip's sizes can lie."""
    target = folder.joinpath(*PurePosixPath(info.filename.replace("\\", "/")).parts)
    if not target.resolve().is_relative_to(folder.resolve()):
        raise ArtefactError(f"the artefact path {info.filename[:80]} leaves the folder; refused.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with opened.open(info) as source, target.open("wb") as destination:
        while chunk := source.read(_CHUNK):
            written += len(chunk)
            if written > max_bytes:
                raise ArtefactError(f"the artefact unpacks to more than {max_bytes} bytes; refused.")
            destination.write(chunk)
    return written
