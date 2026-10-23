# Python Base Guidelines (All Project Types)

**Version**: 2.0 (draft)
**Author**: Richard, personal defaults for AI-assisted Python work
**Supersedes**: 1.0 (see `CHANGELOG.md`)

This file holds what is true for every Python project, whatever it does.
It never names a web framework, a database or a CLI library; those live in the archetype files.
Project-specific overrides in the project's `CLAUDE.md` or `AGENTS.md` always win.

## Before any Python work

- [ ] Read this file in full.
- [ ] Identify the project's archetype and read its file: `PYTHON-CLI.md`, `PYTHON-WEB.md` or `PYTHON-WORKFLOW.md`. If it is not already established, ask.
- [ ] Check the project's `CLAUDE.md`, `AGENTS.md` and `pyproject.toml` for overrides.
- [ ] For a new project, run `scripts/scaffold.py`; for an existing one, run `scripts/audit.py` to see which rules it already meets.

## How to read the tags

Every rule says how it is enforced, so a reader knows what the machine checks and what only a person checks.

- **[tool]** a tool fails the build when it is broken (ruff, pyright, pytest, import-linter, pip-audit in CI).
- **[review]** nothing checks it; code review and the review role must.
- **[gap]** we want a tool for it and do not have one yet.

## 1. Quality

- Type hints on every function signature, parameters and return. [tool: ruff ANN, pyright]
- A docstring on every public function, class and package; one line is enough when it says what and why. [tool: ruff D1]
- No bare `except:`, no `except Exception: pass`; every caught exception is handled, logged or re-raised. [tool: ruff BLE, E722]
- No secrets in code; credentials come from the environment or a gitignored file. [tool: ruff S105, S106; review]
- Timezone-aware datetimes only: `datetime.now(timezone.utc)`, never `utcnow()`. [tool: ruff UP, DTZ if enabled]
- Functions stay under about 30 lines and do one thing; a module that passes about 500 lines, or mixes two jobs, is split. [tool: ruff PLR0915, C90; review]
- Explicit over implicit, standard over novel, simple over complete, tested over theoretical. When two designs work, pick the one a new reader gets first. [review]
- Descriptive names over short ones; comments say why, never what. [review]

## 2. Toolchain

| Concern | Default |
|---|---|
| Language | Python 3.13 or later |
| Packages | uv only: `uv sync`, `uv add`; never `pip install`, `uv pip install` or poetry |
| Config | `pyproject.toml` holds all tool configuration; `uv.lock` is committed |
| Build | hatchling |
| Test | pytest, pytest-cov, pytest-xdist |
| Lint and format | ruff |
| Types | pyright, basic mode first, strict for the core package when it is clean |
| Layering | import-linter, when the project has more than one layer |
| Dependency audit | pip-audit over the locked runtime dependencies |

A new dependency needs a written reason: every dependency is maintenance. [review]

## 3. Layout

- `src/` layout: package code in `src/<package>/`; tests in a top-level `tests/` that mirrors the package. [review]
- Every package's `__init__.py` has a one-line docstring and no logic; there are no empty ones, and no re-exports. [tool: ruff D104]
- A runnable package has `__main__.py`, and a console script in `pyproject.toml` for a tool used often. [review]
- Group by cohesive job, not by technical layer. No `utils`, `common` or `helpers` packages. [review]
- Start with the simplest structure that works, and split when a second thing needs a home. [review]
- Keep pure logic apart from code that touches the world, write down which package may import which, and check it in CI. [tool: import-linter]
- Test helpers live in one `helpers.py`; `conftest.py` holds fixtures only; tests never import from each other. [review]
- Files are `snake_case.py`, classes `PascalCase`, functions and variables `snake_case`, constants `UPPER_SNAKE_CASE`, private names `_leading`. [tool: ruff N if enabled]

## 4. Errors and output

- Expected failures raise a project exception whose message says what is wrong and what to do. Tracebacks are for bugs. When the reader is an agent or a hook, this is not optional (see `PYTHON-CLI.md`).
- `print()` is for a command's result; `logging.getLogger(__name__)` is for diagnostics, with levels used honestly. [tool: ruff T20, with the command modules excepted]
- Never log secrets or whole payloads.

## 5. Data and contracts

- Data crossing a boundary (a file, a database row, a message, an agent's report) is a pydantic model that forbids unknown fields and is frozen. [review]
- Anything persisted carries a schema version. Newer data is refused with a clear message, older data is migrated by explicit adapters, and the bump rule is written down. [review]
- Parse at the edge, and pass typed values inward.

## 6. Subprocesses, files and the network

- Every subprocess and network call has an explicit timeout; a default exists and a caller can pass its own. [gap: no rule yet]
- A subprocess runs in its own process group and is killed as a group on timeout. Avoid `shell=True`; where it is the point, comment why. [tool: ruff S602, S604]
- Open files with an explicit `encoding="utf-8"`; build paths with `pathlib`. [tool: ruff PTH, UP]
- Check a destination exists before writing, and never overwrite what a person may have edited.

## 6a. Databases

- One module owns connections and nothing else opens one; code elsewhere asks it to run a query or a command, and never handles a raw connection. [review]
- SQL is parameterised, never built from strings. [tool: ruff S608]
- **A networked database** (PostgreSQL and the like): one pool per process, created at start-up and sized from settings, with connections borrowed through a context manager that rolls back on error and always returns the connection. Setup cost is the reason a pool exists. `PYTHON-WEB.md` has the pattern; it uses `psycopg2`'s `ThreadedConnectionPool`, and when that file is next migrated, check the current option (psycopg 3 ships its own pool, `psycopg_pool`, and asyncpg has one).
- **An embedded database** (SQLite) in a short-lived command: no pool. Open a connection per operation or per command in the owning module, set its pragmas there (write-ahead logging, synchronous writes when durability matters, a busy timeout), and keep each durable write its own short transaction. Measure before reusing connections: opening one costs microseconds, the durable write costs milliseconds.
- Either way, a failed write rolls back and a closed connection never leaves a transaction open. [review]

## 7. Testing

- Test first: a failing test, then the code. A bug fix starts with a test that reproduces it. [review]
- Assert on behaviour and records, not on whether a mock was called. Replace external tools with small scripted fakes that run as real subprocesses, and use the real thing (git, sqlite) where it is cheap. [review]
- No test needs the network, a credential or a live service. A real end-to-end run is a separate, deliberate step, and "done" is not claimed without one for anything that touches a live system. [review]
- Anything with recovery gets a crash matrix: kill the writer at every write and check no effect repeats. [review]
- A coverage floor in `pyproject.toml` once the project is big enough for it to mean something; choose the number, do not default. [tool: pytest-cov]
- Run in parallel (`pytest -n auto`) in CI. Keep unit and integration tests separable by marker if the suite passes a minute. [tool]

## 8. Security

- No secrets in code or logs; pin or range-pin direct dependencies; audit runtime dependencies in CI. [tool: pip-audit]
- Never show a stack trace to an end user.
- Treat anything from a repository, a file or an agent as untrusted until it is validated.

## 9. The CI baseline

Every pull request runs, in this order: `ruff check`, `ruff format --check`, `pyright`, `lint-imports` (if configured), `pytest -n auto`, and `pip-audit`.
`templates/ci.yml` is that workflow.

## 10. Anti-patterns, hard stops

| About to | Stop because |
|---|---|
| `pip install`, `uv pip install`, poetry | uv only |
| `except:` or `except Exception: pass` | silent failures are bugs |
| Skip a type hint or a docstring | both are required on public names |
| Leave an `__init__.py` empty | give it a docstring saying what the package is |
| Add a `utils` or `common` package | name the job instead |
| Call a subprocess or the network with no timeout | a hang is a failure you cannot see |
| Mock the thing under test | assert on behaviour; use a scripted fake |
| Persist data with no schema version | you will need to migrate it |
| Add an abstraction before the second use | simple first |
| Add a dependency without a reason | maintenance burden |

## 11. Pre-commit checklist

- [ ] Tests pass, and a bug fix has a test that failed first.
- [ ] `ruff check`, `ruff format --check`, `pyright` and `lint-imports` are clean.
- [ ] New public names have type hints and a docstring; new packages have a docstring.
- [ ] No hardcoded secrets; timeouts on every outside call; timezone-aware datetimes.
- [ ] Docs updated (`ARCHITECTURE.md`, the project's standards file) if behaviour changed.
- [ ] Working state only: nothing broken or half done.

## 12. Known gaps

- No rule yet enforces timeouts on outside calls.
- Strict type checking is a goal, not a default.
- Unit and integration tests are not separated unless a project does it.
