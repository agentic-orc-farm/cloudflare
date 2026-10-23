"""AC28: every result.json the live plans and applies write follows schema version 1. Live only."""

import pytest
from tests.acceptance.helpers import Step, result_shape_problems

# The session fixture behind each live plan or apply, by the criterion that runs it.
LIVE_STEPS = {
    "AC15": "prod_plan_only",
    "AC16": "prod_plan_no_artefacts",
    "AC17": "prod_first_apply",
    "AC20": "prod_second_apply",
    "AC21": "prod_plan_after_apply",
    "AC22": "prod_failed_apply",
    "AC29": "collision_apply",
    "AC30": "collision_plan",
    "AC35": "dev_plan",
    "AC36": "dev_first_apply",
    "AC40": "dev_second_apply",
    "AC42": "staging_plan",
}


@pytest.mark.parametrize("criterion", list(LIVE_STEPS))
def test_AC28_live_result_json_follows_schema_version_1(request: pytest.FixtureRequest, criterion: str) -> None:
    request.getfixturevalue("live")
    step: Step = request.getfixturevalue(LIVE_STEPS[criterion])
    run = step.run
    assert run.result_problem is None, run.describe()
    problems = result_shape_problems(run.result, components_empty=criterion in {"AC29", "AC30"})
    assert not problems, f"{problems}\n{run.describe()}"
