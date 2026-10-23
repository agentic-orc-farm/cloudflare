"""AC6 to AC10 and AC23 to AC27: `cf-plane deploy` refuses bad inputs before reading any credential. Offline."""

from collections.abc import Callable

import pytest
from tests.acceptance.helpers import LONG_WORKER, REFUSALS, Refusal, Run, result_shape_problems

BY_CASE = {case.case: case for case in REFUSALS}


def _cases(prefix: str) -> list:
    return [pytest.param(case, id=case.case) for case in REFUSALS if case.case.startswith(prefix + "-")]


def _assert_refused_naming(run: Run, case: Refusal) -> None:
    assert run.exit_code != 0, f"expected a non-zero exit\n{run.describe()}"
    assert run.result_problem is None, run.describe()
    assert isinstance(run.result, dict), run.describe()
    assert run.result.get("components") == [], f"components must be empty\n{run.describe()}"
    missing = [text for text in case.must_name if text not in run.summary]
    assert not missing, f"the summary does not name {missing}\n{run.describe()}"


@pytest.mark.parametrize("case", _cases("AC6"))
def test_AC6_unknown_kind_is_refused_naming_it_and_static_site(refused: Callable, case: Refusal) -> None:
    _assert_refused_naming(refused(case), case)


@pytest.mark.parametrize(
    "case", [pytest.param(case, id=case.case) for case in REFUSALS if case.case.endswith("-without-owner-email")]
)
def test_AC7_dev_and_staging_without_owner_email_are_refused_naming_it(refused: Callable, case: Refusal) -> None:
    assert case.env in {"dev", "staging"}
    _assert_refused_naming(refused(case), case)


def test_AC7_prod_without_credentials_fails_but_does_not_ask_for_the_owner_email(refused: Callable) -> None:
    run = refused(BY_CASE["AC7-prod-without-credentials"])
    assert run.exit_code != 0, f"with no credentials a deploy cannot succeed\n{run.describe()}"
    assert run.result_problem is None, run.describe()
    assert isinstance(run.result, dict) and isinstance(run.result.get("summary"), str), run.describe()
    assert "ACCESS_OWNER_EMAIL" not in run.summary, f"prod needs no owner email\n{run.describe()}"


@pytest.mark.parametrize("case", _cases("AC8"))
def test_AC8_commit_that_is_not_40_lowercase_hex_is_refused(refused: Callable, case: Refusal) -> None:
    _assert_refused_naming(refused(case), case)


@pytest.mark.parametrize("case", _cases("AC9"))
def test_AC9_worker_name_longer_than_63_is_refused_naming_it_and_63(refused: Callable, case: Refusal) -> None:
    assert len(LONG_WORKER) > 63
    run = refused(case)
    assert run.exit_code != 0, run.describe()
    assert run.result_problem is None, run.describe()
    missing = [text for text in case.must_name if text not in run.summary]
    assert not missing, f"the summary does not name {missing}\n{run.describe()}"


@pytest.mark.parametrize("case", _cases("AC23"))
def test_AC23_project_outside_the_organisation_is_refused(refused: Callable, case: Refusal) -> None:
    _assert_refused_naming(refused(case), case)


@pytest.mark.parametrize("case", _cases("AC24"))
def test_AC24_repository_name_with_other_characters_is_refused(refused: Callable, case: Refusal) -> None:
    _assert_refused_naming(refused(case), case)


@pytest.mark.parametrize("case", _cases("AC25"))
def test_AC25_component_for_another_plane_is_refused_naming_it_and_plane(refused: Callable, case: Refusal) -> None:
    _assert_refused_naming(refused(case), case)


@pytest.mark.parametrize("case", _cases("AC26"))
def test_AC26_repeated_component_name_is_refused_naming_it(refused: Callable, case: Refusal) -> None:
    _assert_refused_naming(refused(case), case)


@pytest.mark.parametrize("case", _cases("AC27"))
def test_AC27_malformed_components_are_refused_naming_components(refused: Callable, case: Refusal) -> None:
    _assert_refused_naming(refused(case), case)


@pytest.mark.parametrize("case", [pytest.param(case, id=case.case) for case in REFUSALS])
def test_AC10_refusal_result_json_has_exactly_schema_version_components_and_summary(
    refused: Callable, case: Refusal
) -> None:
    run = refused(case)
    assert run.exit_code != 0, run.describe()
    assert run.result_problem is None, run.describe()
    problems = result_shape_problems(run.result, components_empty=True)
    assert not problems, f"{problems}\n{run.describe()}"
