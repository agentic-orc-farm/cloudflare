# The six targets every project has, as the design's "The make targets" table describes, plus `fixture-site`,
# which ci.yml calls to package the plane's own fixture project. CI runs these and nothing of its own.

.PHONY: setup check test acceptance package smoke fixture-site

setup:
	uv sync --locked
	npm ci

check:
	uv run ruff check
	uv run ruff format --check
	uv run pyright
	uv run lint-imports
	uv run zizmor .github/workflows
	uv export --frozen --no-dev --no-emit-project --no-hashes > requirements-audit.txt
	uv run pip-audit -r requirements-audit.txt --no-deps --disable-pip
	npm audit --omit=dev --audit-level=high

test:
	uv run pytest -n auto tests/unit

# Offline criteria always run; the live ones run only with ACCEPTANCE_LIVE=1, which only acceptance.yml sets.
acceptance:
	uv run pytest tests/acceptance

package:
	@echo "The plane is not packaged: it is never deployed, so it has no artefact."

smoke:
	@echo "The plane has no environments, so there is nothing to smoke-test (ENV=$(ENV))."

# Packages the fixture project for one commit: copies tests/acceptance/fixture-site/ to OUT and writes COMMIT
# to OUT/commit.txt. ci.yml uploads OUT as the artefact `fixture-site`.
fixture-site:
	@test -n "$(COMMIT)" || { echo "fixture-site: set COMMIT to the commit under test" >&2; exit 1; }
	@test -n "$(OUT)" || { echo "fixture-site: set OUT to an empty folder to write the site into" >&2; exit 1; }
	@test -d tests/acceptance/fixture-site || { echo "fixture-site: tests/acceptance/fixture-site/ is missing" >&2; exit 1; }
	rm -rf "$(OUT)"
	mkdir -p "$(OUT)"
	cp -R tests/acceptance/fixture-site/. "$(OUT)/"
	printf '%s' "$(COMMIT)" > "$(OUT)/commit.txt"
