"""The command line, with its commands declared as data (PYTHON-CLI.md section 4)."""

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    """One command: its name, what it does, and the function that runs it."""

    name: str
    help: str
    handler: Callable[[argparse.Namespace], int]


# The build adds `validate`, `deploy` and `wrangler-config` here, as the design's command table says.
COMMANDS: tuple[Command, ...] = ()


def build_parser() -> argparse.ArgumentParser:
    """Build the parser from COMMANDS, so the help lists exactly the commands that exist."""
    parser = argparse.ArgumentParser(prog="cf-plane", description="The Cloudflare plane's shim.")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    for command in COMMANDS:
        sub = subparsers.add_parser(command.name, help=command.help)
        sub.set_defaults(handler=command.handler)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line and return the exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)
