"""The command line, with its commands declared as data (PYTHON-CLI.md section 4), and writing result.json."""

import argparse
import json
import logging
import os
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from cf_plane import access, changes, static_site
from cf_plane.artefacts import Artefact, GitHubArtefacts, unpack
from cf_plane.changes import Plan, Step
from cf_plane.cloudflare import Cloudflare
from cf_plane.contract import Inputs, PlaneError, Refusal, Result, parse_component_config
from cf_plane.wrangler import DEFAULT_WRANGLER
from cf_plane.wrangler import deploy as wrangler_deploy

logger = logging.getLogger(__name__)

# Never handed to wrangler: it needs only the Cloudflare credentials.
_NOT_FOR_WRANGLER = ("GITHUB_READ_TOKEN", "ACCESS_OWNER_EMAIL", "CF_ACCESS_CLIENT_ID", "CF_ACCESS_CLIENT_SECRET")


@dataclass(frozen=True)
class Argument:
    """One required string option of a command."""

    flag: str
    help: str


@dataclass(frozen=True)
class Command:
    """One command: its name, what it does, its options, and the function that runs it."""

    name: str
    help: str
    handler: Callable[[argparse.Namespace], int]
    arguments: tuple[Argument, ...] = ()


# --- Services: everything outside the process, built from the environment or by a test ---------------------------


@dataclass
class Services:
    """The outside world a deploy uses. Built from the environment, or with fakes in the tests."""

    cloudflare: Cloudflare
    github: Callable[[], GitHubArtefacts]
    wrangler: Path
    wrangler_environment: Mapping[str, str] = field(repr=False)
    sleep: Callable[[float], None] = time.sleep

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> "Services":
        """The real services; the Cloudflare credentials are required, the read token only when an apply needs it."""
        token = environment.get("CLOUDFLARE_API_TOKEN")
        account = environment.get("CLOUDFLARE_ACCOUNT_ID")
        if not token or not account:
            raise PlaneError(
                "CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID: not set; deploy reads and changes Cloudflare with "
                "them, and they are secrets of the plane's repository only (README, owner set-up step 4)."
            )
        return cls(
            cloudflare=Cloudflare(token, account),
            github=lambda: GitHubArtefacts(_read_token(environment)),
            wrangler=Path.cwd() / DEFAULT_WRANGLER,
            wrangler_environment={k: v for k, v in environment.items() if k not in _NOT_FOR_WRANGLER},
        )


def _read_token(environment: Mapping[str, str]) -> str:
    token = environment.get("GITHUB_READ_TOKEN")
    if not token:
        raise PlaneError(
            "GITHUB_READ_TOKEN: not set; an apply reads the project's artefacts with it, and the deploy workflow "
            "mints it from the plane's reader App for apply only (README, owner set-up step 6)."
        )
    return token


# --- The deploy run -----------------------------------------------------------------------------------------------


def run_deploy(inputs: Inputs, services: Services, scratch: Path) -> tuple[Result, int]:
    """Observe, compare, and in apply mode change, then return result.json and the exit code."""
    header = changes.header(inputs)
    try:
        plan = _observe_and_compare(inputs, services)
    except PlaneError as error:
        return _refused(header, error), 1
    lines = changes.summary_lines(plan, applied=False)
    for line in lines:
        logger.info("%s", line)
    if inputs.mode == "plan":
        return Result(components=changes.all_components(plan), summary="\n".join([header, *lines])), 0
    steps = changes.apply_steps(plan)
    try:
        artefacts = _locate_artefacts(plan, services)
    except PlaneError as error:
        return _refused(header, error), 1
    executor = _Executor(plan, services, artefacts, scratch)
    for index, step in enumerate(steps):
        try:
            executor.run(step)
        except PlaneError as error:
            summary = [
                header,
                f"{step.target or step.action}: failed: {error}",
                "Nothing after that step was done; run the same apply again to finish it.",
            ]
            return Result(components=changes.live_components(plan, steps, index), summary="\n".join(summary)), 1
    applied = changes.summary_lines(plan, applied=True)
    return Result(components=changes.all_components(plan), summary="\n".join([header, *applied])), 0


def _refused(header: str, error: PlaneError) -> Result:
    return Result(components=(), summary=f"{header}: refused, nothing changed\n{error}")


def _observe_and_compare(inputs: Inputs, services: Services) -> Plan:
    names = changes.worker_names(inputs)
    logger.info("reading the workers.dev subdomain and %d Worker(s)", len(names))
    subdomain = services.cloudflare.workers_subdomain()
    workers = services.cloudflare.observe_workers(names.values())
    observed_access = None
    if inputs.private:
        logger.info("reading the account's Access policies, applications, service tokens and login methods")
        observed_access = services.cloudflare.observe_access()
    return changes.compare(inputs, subdomain, workers, observed_access)


def _locate_artefacts(plan: Plan, services: Services) -> dict[str, Artefact]:
    """Find every artefact an apply will deploy before changing anything, so a missing one changes nothing."""
    needed = [change for change in plan.components if change.deploy]
    if not needed:
        return {}
    github = services.github()
    found = {}
    for change in needed:
        artefact = change.component.artefact
        logger.info("%s: finding artefact %s for commit %s", change.component.name, artefact, plan.inputs.commit)
        found[change.component.name] = github.find(plan.inputs.project, artefact, plan.inputs.commit)
    return found


class _Executor:
    """Runs an apply's steps one by one, logging before and after each outside effect."""

    def __init__(self, plan: Plan, services: Services, artefacts: dict[str, Artefact], scratch: Path) -> None:
        self._plan = plan
        self._services = services
        self._artefacts = artefacts
        self._scratch = scratch
        self._policy_ids = {policy.name: policy.policy_id for policy in plan.policies}
        self._worker_ids = {change.component.name: change.worker_id for change in plan.components}
        self._unpacked: dict[str, Path] = {}

    def run(self, step: Step) -> None:
        """Run one step."""
        handlers = {
            "policy": self._policy,
            "deploy": self._deploy,
            "app": self._app,
            "wait": self._wait,
            "enable": self._enable,
        }
        handlers[step.action](step)

    def _policy(self, step: Step) -> None:
        change = self._plan.policy(step.target)
        policy_id = change.policy_id
        logger.info("Access policy %s: %s", change.name, "creating" if policy_id is None else "updating")
        if policy_id is None:
            self._policy_ids[change.name] = self._services.cloudflare.create_policy(change.body)
        else:
            self._services.cloudflare.update_policy(policy_id, change.body)
        logger.info("Access policy %s: done", change.name)

    def _deploy(self, step: Step) -> None:
        change = self._plan.component(step.target)
        folder = self._assets(step.target)
        config = static_site.wrangler_config(change.worker, folder, workers_dev=step.workers_dev)
        logger.info("%s: deploying Worker %s (workers.dev %s)", step.target, change.worker, step.workers_dev)
        wrangler_deploy(
            config,
            change.marker,
            wrangler=self._services.wrangler,
            work_dir=self._scratch / "wrangler" / step.target,
            environment=self._services.wrangler_environment,
        )
        logger.info("%s: deployed Worker %s", step.target, change.worker)

    def _assets(self, name: str) -> Path:
        if name not in self._unpacked:
            artefact = self._artefacts[name]
            archive = self._scratch / f"{name}.zip"
            logger.info("%s: downloading artefact %s", name, artefact.name)
            self._services.github().download(self._plan.inputs.project, artefact, archive)
            (self._scratch / "assets").mkdir(exist_ok=True)
            self._unpacked[name] = unpack(archive, self._scratch / "assets" / name)
            logger.info("%s: unpacked artefact %s", name, artefact.name)
        return self._unpacked[name]

    def _app(self, step: Step) -> None:
        change = self._plan.component(step.target)
        worker_id = self._worker_ids.get(step.target) or self._services.cloudflare.worker_id(change.worker)
        service_id = self._policy_ids.get(access.SERVICE_TOKEN_POLICY)
        owner_id = self._policy_ids.get(access.OWNER_POLICY)
        if not worker_id or not service_id or not owner_id or not self._plan.one_time_pin_id:
            raise PlaneError(f"the Worker {change.worker} or a shared policy has no id yet; run the apply again.")
        body = static_site.access_application(
            change.worker, worker_id, (service_id, owner_id), self._plan.one_time_pin_id
        )
        logger.info(
            "%s: %s Access application %s",
            step.target,
            "creating" if change.app_id is None else "updating",
            change.worker,
        )
        if change.app_id is None:
            self._services.cloudflare.create_app(body)
        else:
            self._services.cloudflare.update_app(change.app_id, body)
        logger.info("%s: Access application %s done", step.target, change.worker)

    def _wait(self, step: Step) -> None:
        logger.info("waiting %d seconds for the new Access application(s) to take effect", step.seconds)
        self._services.sleep(step.seconds)

    def _enable(self, step: Step) -> None:
        change = self._plan.component(step.target)
        logger.info("%s: turning workers.dev on, previews off, for Worker %s", step.target, change.worker)
        self._services.cloudflare.enable_workers_dev(change.worker)
        logger.info("%s: Worker %s is at %s", step.target, change.worker, change.url)


# --- The commands -------------------------------------------------------------------------------------------------


def _write_result(path: str, result: Result) -> None:
    destination = Path(path)
    if not destination.parent.is_dir():
        raise SystemExit(f"--result: the folder {destination.parent} does not exist")
    destination.write_text(result.to_json(), encoding="utf-8")


def _validated(args: argparse.Namespace) -> Inputs:
    """Validation reads only PLANE_ORG and ACCESS_OWNER_EMAIL, so it refuses before any credential is read."""
    return changes.validate(
        project=args.project,
        commit=args.commit,
        env=args.env,
        mode=args.mode,
        components=args.components,
        plane_org=os.environ.get("PLANE_ORG"),
        owner_email=os.environ.get("ACCESS_OWNER_EMAIL"),
    )


def _refuse(args: argparse.Namespace, refusal: Refusal) -> int:
    _write_result(args.result, Result(components=(), summary=str(refusal)))
    print(str(refusal), file=sys.stderr)
    return 1


def validate_command(args: argparse.Namespace) -> int:
    """Check the inputs; print the repository name, or write result.json and exit 1."""
    try:
        inputs = _validated(args)
    except Refusal as refusal:
        return _refuse(args, refusal)
    print(inputs.repo)
    return 0


def deploy_command(args: argparse.Namespace) -> int:
    """Validate, then plan or apply, and write result.json."""
    try:
        inputs = _validated(args)
    except Refusal as refusal:
        return _refuse(args, refusal)
    try:
        services = Services.from_environment(os.environ)
    except PlaneError as error:
        result, exit_code = _refused(changes.header(inputs), error), 1
    else:
        with tempfile.TemporaryDirectory(prefix="cf-plane-") as scratch:
            result, exit_code = run_deploy(inputs, services, Path(scratch))
    _write_result(args.result, result)
    print(result.summary, file=sys.stderr if exit_code else sys.stdout)
    return exit_code


def wrangler_config_command(args: argparse.Namespace) -> int:
    """Print one component's wrangler configuration, with no credentials and no network."""
    try:
        repo, component = parse_component_config(args.project, args.env, args.component, changes.KINDS.keys())
        worker = static_site.worker_name(repo, component.name, args.env)
    except Refusal as refusal:
        print(str(refusal), file=sys.stderr)
        return 1
    print(json.dumps(static_site.wrangler_config(worker, Path(args.assets)), indent=2))
    return 0


_INPUTS = (
    Argument("--project", "the project, owner/repo"),
    Argument("--commit", "the commit's full sha"),
    Argument("--env", "dev, staging or prod"),
    Argument("--mode", "plan or apply"),
    Argument("--components", "a JSON list of the project's deploy.yaml entries for this plane"),
    Argument("--result", "where to write result.json"),
)

COMMANDS: tuple[Command, ...] = (
    Command("validate", "check the inputs and print the repository name", validate_command, _INPUTS),
    Command("deploy", "plan or apply the components, and write result.json", deploy_command, _INPUTS),
    Command(
        "wrangler-config",
        "print one component's wrangler configuration (no credentials, no network)",
        wrangler_config_command,
        (
            Argument("--project", "the project, owner/repo"),
            Argument("--env", "dev, staging or prod"),
            Argument("--component", "one deploy.yaml entry as a JSON object"),
            Argument("--assets", "the folder of the unpacked artefact"),
        ),
    ),
)


def build_parser() -> argparse.ArgumentParser:
    """Build the parser from COMMANDS, so the help lists exactly the commands that exist."""
    parser = argparse.ArgumentParser(prog="cf-plane", description="The Cloudflare plane's shim.")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    for command in COMMANDS:
        sub = subparsers.add_parser(command.name, help=command.help)
        for argument in command.arguments:
            sub.add_argument(argument.flag, required=True, help=argument.help)
        sub.set_defaults(handler=command.handler)
    return parser


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    # httpx logs every request's URL at INFO, and a Cloudflare URL holds the account id.
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line and return the exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    _configure_logging()
    return handler(args)
