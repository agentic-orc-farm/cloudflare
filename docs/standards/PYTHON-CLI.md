# Python CLI / Batch / Script Tool Guidelines

**Version**: 2.0 (draft)
**Scope**: a standalone script, CLI tool or batch job with no web framework and usually no database, invoked manually or on a trigger. If a tool is driven by agents or hooks rather than a person, the section on agent-facing tools applies too.
Read `PYTHON-BASE.md` first; it holds every rule that is not specific to this archetype.

## Before any CLI work

- [ ] Read `PYTHON-BASE.md` and this file in full.
- [ ] Check the project's `CLAUDE.md`, `AGENTS.md` and `pyproject.toml` for overrides.
- [ ] Ask about anything on the list below that the project has not already answered.

## Ask before assuming

- **Config**: a JSON, YAML or TOML file, environment variables, or both?
- **Trigger**: manual only, or cron, launchd or a wake check? Never assume a fixed-time schedule is reliable on a laptop; prefer an idempotency check on wake.
- **Idempotency**: can it run twice safely, and what is the guard?
- **Output**: stdout, a file, an external system? A write to a real personal system needs the care in section 5.
- **Failure**: should one failed step abort the run, or degrade and report?
- **Consumer**: a person at a terminal, or an agent or hook? That decides the error style (section 2).

## 1. Output and logging

- `print()` is for the tool's deliverable: the thing someone runs it to get. Everything diagnostic goes through `logging.getLogger(__name__)`.
- A five-function script needs no logging setup. Add real logging when there are enough moving parts that "what happened in that run" becomes a question.
- Fail loud. A tool that swallows an error to keep output clean hides what its operator needs to see.

## 2. Errors: by who reads them

- **One person at a terminal**: letting an exception propagate with its traceback is fine; the traceback is the diagnostic. Do not build a friendly-error layer for one user.
- **An agent or a hook** (any tool another program drives): raise a project exception with a short message that says what is wrong and what to do, print it to stderr, and exit non-zero. No tracebacks for expected failures; a traceback is a bug. Make the message safe to paste back into a prompt.
- Either way, exit non-zero on failure so a caller can detect it.
- Where one independent step's failure should not abort the rest, say so in code or docs and handle it deliberately. Do not add per-step resilience "just in case".

## 3. Agent-facing tools

When agents drive the tool:

- Every command is idempotent or says plainly that it is not, and records an intent before an outside effect and a result after.
- Offer `--json` where a program reads the output, and keep the human line stable where a person does.
- A refusal says which rule refused and what would satisfy it.
- Commands that approve, override or delete are separate commands, so a permission system can prompt for them by name.
- Nothing an agent can reach should apply an outside change without an owner's approval recorded first.

## 4. Structure and entry points

```
my-tool/
  pyproject.toml
  src/my_tool/
    __init__.py        # one-line docstring
    __main__.py        # python -m my_tool
    cli.py             # parser and commands
    <feature modules>.py
  tests/
    helpers.py
    conftest.py        # fixtures only
    test_<module>.py
```

- Declare commands as data (a table of name, handler and arguments) and build the parser from it, instead of long runs of `add_parser` and `add_argument` calls. Derive the command list shown in help; a hand-kept list drifts. Pin the command surface in a test.
- Declare a console script in `pyproject.toml` (`my-tool = "my_tool.cli:main"`); `__main__.py` is three lines that call the same `main`.
- Config that is structured or variable-length goes in a file under `config/`, loaded by a small `config.py`; a dataclass is enough until nesting or cross-field rules make pydantic worth it.
- Decide "config or constant?" for each value at design time. Per-deployment values (paths, endpoints, per-item settings) are config.
- If several items share a mechanism, implement it once, parameterised by config, instead of one near-duplicate module per item.

## 5. Writing to real systems

- Check the destination exists before writing; do not let `mkdir(parents=True)` invent a wrong path and report success. Create only what the tool owns.
- Never overwrite what a person may have edited. Check for existing state and skip or merge.
- Encode text explicitly as UTF-8.
- A scheduled run gets the same guarantees as a manual one; a background trigger firing often is when a naive overwrite does the most damage.

## 6. Fetching external data

- An explicit timeout on every network call, and `raise_for_status()` rather than carrying on after a 404, 500 or 429.
- Filter for genuine recency when a source can serve stale content; check the source's own timestamp, not just "I got a response".
- Verify a fetch mechanism against the live source during design; sites change and some block scraping.

## 7. Testing

- Network and outside tools are always faked in the automated suite; the suite never needs a live service.
- A real run against live systems is a separate, deliberate step, and is not claimed done without it.
- Test recency and staleness logic explicitly; "all green" can hide it when every fixture is fresh.

## 8. Anti-patterns

| About to | Stop because |
|---|---|
| `print()` a diagnostic, warning or error | `logging` is for that; `print` is for the result |
| Show an agent a traceback for an expected failure | give a short, actionable message and a non-zero exit |
| Hardcode a per-deployment path or URL | it is config |
| Write one module per item without checking for a shared mechanism | duplicated modules are a smell |
| Let `mkdir(parents=True)` create a destination that should exist | assert it first |
| Overwrite output unconditionally | a person may have touched it |
| Claim a fetch works from documentation alone | verify against the live source |
| Claim done without a live run | mocks prove the code, not the integration |

## 9. Pre-commit additions

- [ ] Config-worthy values live in config, not constants.
- [ ] Network and tools are faked in the suite.
- [ ] A write path is guarded against a wrong location and against clobbering state.
- [ ] If it runs on a trigger, the second-run behaviour is explicit.
- [ ] If agents drive it, errors are short messages with exit codes, and approvals are separate commands.
- [ ] A real manual run has been done at least once if it touches a live system.
