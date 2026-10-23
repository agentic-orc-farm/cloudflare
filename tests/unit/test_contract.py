import json

import pytest

from cf_plane.contract import (
    Refusal,
    Result,
    ResultComponent,
    fit_summary,
    parse_component_config,
    parse_inputs,
    quote,
)

ORG = "agentic-orc-farm"
COMMIT = "4f2b9c0d1e3a5b7c9d0e2f4a6b8c0d2e4f6a8b0c"
SITE = {"name": "site", "kind": "static-site", "plane": "cloudflare", "artefact": "site"}


def parse(**overrides: object):
    arguments: dict = {
        "project": f"{ORG}/example",
        "commit": COMMIT,
        "env": "prod",
        "mode": "plan",
        "components": json.dumps([SITE]),
        "plane_org": ORG,
        "owner_email": None,
        "kinds": ("static-site",),
    }
    arguments.update(overrides)
    return parse_inputs(**arguments)


def refusal_of(**overrides: object) -> str:
    with pytest.raises(Refusal) as caught:
        parse(**overrides)
    return str(caught.value)


def test_valid_inputs_become_typed_values() -> None:
    inputs = parse()
    assert inputs.project == f"{ORG}/example"
    assert inputs.owner == ORG
    assert inputs.repo == "example"
    assert inputs.private is False
    assert [component.name for component in inputs.components] == ["site"]


def test_dev_with_an_owner_email_is_private_and_keeps_the_email() -> None:
    inputs = parse(env="dev", owner_email="owner@example.com")
    assert inputs.private is True
    assert inputs.owner_email == "owner@example.com"


def test_prod_ignores_the_owner_email() -> None:
    assert parse(owner_email="owner@example.com").owner_email is None


def test_plane_org_unset_is_refused_naming_it() -> None:
    assert "PLANE_ORG" in refusal_of(plane_org=None)


def test_project_of_another_organisation_is_refused() -> None:
    message = refusal_of(project="someone-else/example")
    assert "project" in message
    assert ORG in message


@pytest.mark.parametrize("project", ["example", f"{ORG}/", f"{ORG}/a/b", f"{ORG}/My.Site", f"{ORG}/my_site"])
def test_malformed_project_is_refused(project: str) -> None:
    assert refusal_of(project=project).startswith("project:")


@pytest.mark.parametrize("commit", ["4f2b9c0", COMMIT.upper(), "g" * 40, COMMIT + "0"])
def test_commit_that_is_not_40_lowercase_hex_is_refused(commit: str) -> None:
    assert refusal_of(commit=commit).startswith("commit:")


def test_unknown_env_and_mode_are_refused() -> None:
    message = refusal_of(env="qa", mode="destroy")
    assert "env:" in message
    assert "mode:" in message


@pytest.mark.parametrize("env", ["dev", "staging"])
def test_private_env_without_owner_email_is_refused(env: str) -> None:
    assert "ACCESS_OWNER_EMAIL" in refusal_of(env=env)


@pytest.mark.parametrize("email", ["pinholder", "a@b@c", "pin holder@example.com", "@example.com", "pinholder@"])
def test_private_env_with_a_malformed_owner_email_is_refused_without_echoing_it(email: str) -> None:
    message = refusal_of(env="staging", owner_email=email)
    assert "ACCESS_OWNER_EMAIL" in message
    assert email not in message


def test_prod_without_owner_email_does_not_mention_it() -> None:
    message = refusal_of(commit="short")
    assert "ACCESS_OWNER_EMAIL" not in message


@pytest.mark.parametrize("text", ["[{not json", "[]", "{}", '"site"', "null"])
def test_components_that_are_not_a_non_empty_list_are_refused(text: str) -> None:
    assert refusal_of(components=text).startswith("components:")


@pytest.mark.parametrize(
    "item",
    [
        {"name": "site", "kind": "static-site", "plane": "cloudflare"},
        {**SITE, "region": "eu"},
        "site",
        {**SITE, "name": "Site"},
        {**SITE, "artefact": ""},
        {**SITE, "name": 3},
        {**SITE, "name": "-site"},
    ],
)
def test_malformed_component_items_are_refused(item: object) -> None:
    assert "components:" in refusal_of(components=json.dumps([item]))


def test_component_for_another_plane_is_refused_naming_it_and_plane() -> None:
    message = refusal_of(components=json.dumps([{**SITE, "name": "brochure", "plane": "aws"}]))
    assert "brochure" in message
    assert "plane" in message


def test_unknown_kind_is_refused_naming_it_and_the_kinds_offered() -> None:
    message = refusal_of(components=json.dumps([{**SITE, "kind": "edge-function"}]))
    assert "edge-function" in message
    assert "static-site" in message


def test_repeated_component_names_are_refused_naming_the_name() -> None:
    message = refusal_of(components=json.dumps([{**SITE, "name": "landing"}, {**SITE, "name": "landing"}]))
    assert "landing" in message


def test_every_problem_is_reported_at_once() -> None:
    message = refusal_of(commit="short", env="qa")
    assert "commit:" in message
    assert "env:" in message


def test_quote_shortens_and_escapes_untrusted_text() -> None:
    assert quote("a\nb") == '"a\\nb"'
    long = quote("x" * 500)
    assert len(long) < 100
    assert long.endswith('..."')


def test_result_json_has_exactly_the_three_keys() -> None:
    result = Result(components=(ResultComponent(name="site", url="https://x"),), summary="line")
    assert json.loads(result.to_json()) == {
        "schema_version": 1,
        "components": [{"name": "site", "url": "https://x"}],
        "summary": "line",
    }


def test_result_summary_is_fitted_to_1000_characters() -> None:
    summary = "\n".join(f"line {index} " + "x" * 50 for index in range(100))
    result = Result(components=(), summary=summary)
    assert len(json.loads(result.to_json())["summary"]) <= 1000


def test_fit_summary_keeps_whole_lines_and_says_how_many_more() -> None:
    lines = ["first"] + [f"line {index:02d} " + "y" * 40 for index in range(60)]
    fitted = fit_summary("\n".join(lines))
    kept = fitted.splitlines()
    assert len(fitted) <= 1000
    assert kept[0] == "first"
    assert kept[-1] == f"({len(lines) - (len(kept) - 1)} more lines: see the run log)"
    assert all(line in lines for line in kept[:-1])


def test_fit_summary_leaves_a_short_summary_alone() -> None:
    assert fit_summary("one\ntwo") == "one\ntwo"


def test_fit_summary_cuts_a_single_overlong_first_line() -> None:
    fitted = fit_summary("z" * 3000)
    assert len(fitted) <= 1000


def test_a_component_configuration_needs_no_plane_org() -> None:
    repo, parsed = parse_component_config(f"{ORG}/example", "prod", json.dumps(SITE), ("static-site",))
    assert repo == "example"
    assert parsed.name == "site"


@pytest.mark.parametrize(
    ("project", "env", "item", "named"),
    [
        ("example", "prod", SITE, "project:"),
        (f"{ORG}/My.Site", "prod", SITE, "project:"),
        (f"{ORG}/example", "qa", SITE, "env:"),
        (f"{ORG}/example", "prod", {**SITE, "kind": "worker"}, "worker"),
        (f"{ORG}/example", "prod", {"name": "site"}, "components:"),
    ],
)
def test_a_bad_component_configuration_is_refused(project: str, env: str, item: dict, named: str) -> None:
    with pytest.raises(Refusal) as caught:
        parse_component_config(project, env, json.dumps(item), ("static-site",))
    assert named in str(caught.value)


def test_a_component_configuration_that_is_not_one_json_object_is_refused() -> None:
    with pytest.raises(Refusal, match="components:"):
        parse_component_config(f"{ORG}/example", "prod", "{}, {}", ("static-site",))
