# Git & GitHub Workflow Guidelines

**Version**: 2.0 (draft)
**Author**: Richard, personal preferences for AI-assisted git and GitHub workflow
**Supersedes**: 1.0 (see `CHANGELOG.md`)

This file covers branching, worktrees, commits, pull requests, versioning, releases and CI/CD conventions for any language or stack.
Language rules live in `PYTHON-BASE.md`, `UI.md` and `SWIFT.md`; the CI baseline for Python is in `PYTHON-BASE.md` section 9.
A project's own `AGENTS.md` or `CLAUDE.md` always wins over this file.

## Before setting up branching, CI or releases

- [ ] Read this file in full.
- [ ] Check the project's `AGENTS.md`, `CLAUDE.md` and `ARCHITECTURE.md` for overrides.
- [ ] Ask about anything below that the project has not already answered.

## Ask before assuming

- **Who does the work**: only people, AI agents, or both? Agents change the defaults for pull requests and protection (section 4).
- **Team size**: solo, or several contributors?
- **Deployment**: none, the repository's own CI/CD, or an artifact deployed by something else? And to how many environments?
- **Release cadence**: continuous, periodic tags, or none?
- **Distribution**: does it ever leave the developer's machine or organisation?

Do not invent answers. Ask once, clearly.

## 1. Branching

- **Trunk-based** by default: `main` is always releasable, and every change reaches it on a short-lived branch, merged promptly. [review]
- No `develop` and no `release/*` branches. Environments are reached by promoting the same build, not by branches (section 7). [review]
- Branch names are `type/short-description`, with types `feat`, `fix`, `chore`, `refactor`, `docs`, `test`: `feat/run-lock`, `refactor/layout`. [review]
- **GitFlow-style** (`develop`, `release/*`, `hotfix/*`) is for a legacy project that already deploys by branch, or a team with a real reason. Say so in the project's `AGENTS.md`; do not drift into it.

## 2. Worktrees

- Do each change in its own worktree under `.worktrees/` inside the repository, and keep the main checkout on `main`. [review]
- `.worktrees/` is git-ignored: `git worktree add .worktrees/my-change -b feat/my-change main`.
- A worktree is removed when its change merges, so there are only ever a few. Each has its own virtual environment; run the project's install command in it.
- Tools that agents run (ruff, pytest, type checkers) are pointed at tracked folders and so do not scan `.worktrees/`; check this when adding a tool.
- A tool that creates worktrees for its own runs, such as the orchestrator, keeps them outside the repository, in `<repository>-worktrees/<run-id>/`. That is a separate thing.

## 3. Commits

- The subject is `area: what changed`, in the imperative or as a plain statement, ideally under about 72 characters: `journal: a schema version with migration adapters`. The area is the part of the project it touches (`core`, `cli`, `docs`, `tooling`, `layout`, `cleanup`, `ci`). [review]
- The body says why, one sentence per line, and is where the pull request description lives (section 4). [review]
- **No trailers that name an AI assistant**: no `Co-authored-by`, no "generated with". [review]
- **Conventional Commits** (`feat(scope): ...`) only when something consumes them, such as a release tool that builds a changelog. If a project does that, its `AGENTS.md` says so and the types are then required. [review]
- Never hand-edit a generated file, `CHANGELOG.md` included. [review]

## 4. Pull requests

- **Everything goes through a pull request**, even on a solo project, when AI agents do any of the work: the pull request is where CI runs and where a change is reviewed before it lands. Do not push to `main`. [review]
- The title is the last commit's subject and the description is its body, so the description is written once, in the commit. [review]
- One concern per pull request, small enough to review and to revert.
- **Squash-merge**, so `main` has one commit per change, with the pull request number appended. [review]
- Protect `main`: require a pull request and the CI checks, and no direct pushes, including for the owner. Agents never merge unless explicitly asked; the owner merges, or runs the repository's merge script. [review]
- A repository can carry `scripts/merge-worktree-via-pr.sh`: it pushes the worktree's branch, opens the pull request from the last commit, waits for CI, squash-merges and removes the worktree.

## 5. Versioning

- **Semantic Versioning** for anything others depend on: `0.x.y` until the first stable scope is in real use, `MAJOR` for a breaking change to any public contract, `MINOR` for compatible new behaviour, `PATCH` for fixes.
- Calendar versions (`v2026.014`) suit a site or an application nobody imports, where "what is live" matters more than compatibility.
- Where the number lives: `pyproject.toml` (Python), `package.json` (Node), `Cargo.toml` (Rust), `CFBundleShortVersionString` and `CFBundleVersion` (Swift).

## 6. Tags and releases

- Tag `main` often enough that what is running is always traceable to a commit.
- A GitHub Release, with notes and attached builds, is for something you hand to someone else. For personal software a tag is enough.
- Do not build release automation, changelog generation or version-bump bots until the lack of it is causing friction. If a project adopts them, it also adopts Conventional Commits (section 3).

## 7. CI and CD

CI proves a change is good; CD puts a good change somewhere. Keep them apart.

- **CI on every pull request**: tests, lint and type checks, plus the language baseline (`PYTHON-BASE.md` section 9). Never merge on red. [tool: required checks]
- **Pin actions to a version and keep them current.** An outdated action starts to warn, then fails, when its runtime is retired. [review]
- **Least privilege**: set `permissions:` in each workflow to what it needs, usually `contents: read`.
- **Secrets** live in the CI or cloud secret store, never in the repository or a log, and only the job that needs one gets it.
- **Build once.** CI produces one immutable artifact (a static bundle, a container image) for a commit, and every environment receives that same artifact. [review]
- **Environments are reached by promotion**, not by branch: the same artifact goes to staging, then production, with production approved by the owner.
- **Who deploys is a per-project decision** that the project records: the repository's own workflow, or a separate deployment tool that takes the artifact and a target. Provider-specific details (Cloudflare, AWS, Kubernetes) belong in that tool or in the project, not in this file.
- A project that already deploys by branch (`develop` to staging, `main` to production) may keep doing so; it should say so, and not be used as the model for new work.

| Project shape | CI | CD |
|---|---|---|
| Personal tool | tests and lint on every PR | local install |
| Site or service, one environment | as above | deploy the merged commit's artifact |
| Several environments | as above | promote one artifact, production by approval |

## 8. Repository hygiene

- `.gitignore` covers at least `.DS_Store`, `__pycache__/`, `.venv/`, `.worktrees/`, `.coverage`, `dist/`, `*.egg-info/`, `node_modules/` and tool caches; bare names match at any depth.
- Generated files are marked as generated and never edited by hand.
- The default branch is protected from the day the repository is created.

## For AI assistants

1. Read this file before creating branches, worktrees, CI workflows or anything release-related.
2. Work in a worktree under `.worktrees/`; never on `main`.
3. Write the pull request description in the last commit message. No co-author or "generated by" trailers.
4. Never push to `main`, and never merge unless the owner asked. Open the pull request or leave the branch ready.
5. Never hand-edit generated files, including `CHANGELOG.md`.
6. Do not default into GitFlow, release automation or a particular deployment tool; ask if the deployment shape is unclear.
7. Check the project's `AGENTS.md` for overrides.

## Known gaps

- The deployment model (artifact and a separate deployment tool) is a direction, not yet a settled design; this file will be updated when it is.
- There is no ruleset template for branch protection yet.
