"""AC1 to AC4, AC32 and AC33: the workflows' wiring, read from .github/workflows/. Offline."""

import re

import pytest
from tests.acceptance.helpers import WORKFLOWS, expression_mentions, load_workflow, steps, triggers, workflow_files

DEPLOY = WORKFLOWS / "deploy.yml"
ACCEPTANCE = WORKFLOWS / "acceptance.yml"
DEPLOY_INPUTS = {"project", "commit", "env", "mode", "components"}
SECRET_HOLDERS = {"deploy.yml", "acceptance.yml"}
UNTRUSTED_TRIGGERS = {"pull_request", "pull_request_target", "push"}


def _deploy() -> dict:
    assert DEPLOY.is_file(), ".github/workflows/deploy.yml does not exist"
    return load_workflow(DEPLOY)


def _acceptance() -> dict:
    assert ACCEPTANCE.is_file(), ".github/workflows/acceptance.yml does not exist"
    return load_workflow(ACCEPTANCE)


def _dispatch_inputs(workflow: dict) -> dict:
    dispatch = triggers(workflow).get("workflow_dispatch") or {}
    return dispatch.get("inputs") or {}


# --- AC1 ----------------------------------------------------------------------------------------------------


def test_AC1_deploy_workflow_is_named_deploy() -> None:
    assert _deploy().get("name") == "deploy"


def test_AC1_deploy_workflow_is_started_only_by_workflow_dispatch() -> None:
    assert set(triggers(_deploy())) == {"workflow_dispatch"}


def test_AC1_deploy_workflow_has_exactly_the_five_inputs_all_required() -> None:
    inputs = _dispatch_inputs(_deploy())
    assert set(inputs) == DEPLOY_INPUTS
    not_required = [name for name, spec in inputs.items() if (spec or {}).get("required") is not True]
    assert not not_required, f"inputs not marked required: true: {not_required}"


def test_AC1_env_input_is_a_choice_of_dev_staging_and_prod() -> None:
    env = _dispatch_inputs(_deploy()).get("env") or {}
    assert env.get("type") == "choice"
    assert sorted(env.get("options") or []) == ["dev", "prod", "staging"]


def test_AC1_mode_input_is_a_choice_of_plan_and_apply() -> None:
    mode = _dispatch_inputs(_deploy()).get("mode") or {}
    assert mode.get("type") == "choice"
    assert sorted(mode.get("options") or []) == ["apply", "plan"]


# --- AC2 ----------------------------------------------------------------------------------------------------


def test_AC2_result_json_is_uploaded_as_the_artefact_result_even_after_a_failure() -> None:
    uploads = [
        step
        for _, step in steps(_deploy())
        if str(step.get("uses", "")).startswith("actions/upload-artifact@")
        and str((step.get("with") or {}).get("name", "")) == "result"
    ]
    assert uploads, "no actions/upload-artifact step uploads an artefact named `result`"
    good = [
        step
        for step in uploads
        if str((step.get("with") or {}).get("path", "")).strip().endswith("result.json")
        and re.fullmatch(r"(\$\{\{\s*)?always\(\)(\s*\}\})?", str(step.get("if", "")).strip())
    ]
    assert good, f"the `result` upload must have path result.json and `if: always()`; found {uploads}"


# --- AC3 ----------------------------------------------------------------------------------------------------


def test_AC3_concurrency_group_is_built_from_project_and_env_and_does_not_cancel() -> None:
    workflow = _deploy()
    blocks = [workflow.get("concurrency")] + [
        (job or {}).get("concurrency") for job in (workflow.get("jobs") or {}).values()
    ]
    blocks = [block for block in blocks if block]
    assert blocks, "deploy.yml has no concurrency setting"
    good = [
        block
        for block in blocks
        if isinstance(block, dict)
        and expression_mentions(str(block.get("group", "")), "project")
        and expression_mentions(str(block.get("group", "")), "env")
        and block.get("cancel-in-progress") is False
    ]
    assert good, (
        f"no concurrency block has a group from inputs.project and inputs.env with cancel-in-progress false: {blocks}"
    )


# --- AC4 ----------------------------------------------------------------------------------------------------

INPUT_IN_EXPRESSION = re.compile(r"\$\{\{[^}]*?(?<![\w.])(github\.event\.)?inputs\.", re.DOTALL)


def _workflows_to_check() -> list[str]:
    names = {path.name for path in workflow_files()}
    return sorted(names | SECRET_HOLDERS)


@pytest.mark.parametrize("name", _workflows_to_check())
def test_AC4_no_run_block_reads_an_input_directly(name: str) -> None:
    path = WORKFLOWS / name
    assert path.is_file(), f".github/workflows/{name} does not exist"
    offending = [
        f"{job}: {step.get('name') or step['run'][:60]!r}"
        for job, step in steps(load_workflow(path))
        if "run" in step and INPUT_IN_EXPRESSION.search(str(step["run"]))
    ]
    assert not offending, f"run: blocks in {name} that read inputs inside ${{{{ }}}}: {offending}"


# --- AC32 ---------------------------------------------------------------------------------------------------


def test_AC32_acceptance_workflow_is_named_acceptance_and_started_only_by_workflow_dispatch() -> None:
    workflow = _acceptance()
    assert workflow.get("name") == "acceptance"
    assert set(triggers(workflow)) == {"workflow_dispatch"}


def test_AC32_acceptance_workflow_has_exactly_one_required_input_commit() -> None:
    inputs = _dispatch_inputs(_acceptance())
    assert set(inputs) == {"commit"}
    assert (inputs["commit"] or {}).get("required") is True


def test_AC32_acceptance_run_name_carries_the_commit() -> None:
    assert expression_mentions(str(_acceptance().get("run-name", "")), "commit")


def test_AC32_acceptance_workflow_checks_out_the_commit() -> None:
    checkouts = [
        step
        for _, step in steps(_acceptance())
        if str(step.get("uses", "")).startswith("actions/checkout@")
        and expression_mentions(str((step.get("with") or {}).get("ref", "")), "commit")
    ]
    assert checkouts, "no actions/checkout step with `ref` set to inputs.commit"


# --- AC33 ---------------------------------------------------------------------------------------------------


def test_AC33_no_workflow_started_by_pull_request_or_push_mentions_secrets() -> None:
    offending = [
        path.name
        for path in workflow_files()
        if set(triggers(load_workflow(path))) & UNTRUSTED_TRIGGERS and "secrets." in path.read_text()
    ]
    assert not offending, f"workflows started by pull_request or push that mention secrets.: {offending}"


def test_AC33_no_workflow_is_started_by_pull_request_target() -> None:
    offending = [path.name for path in workflow_files() if "pull_request_target" in triggers(load_workflow(path))]
    assert not offending


def test_AC33_only_deploy_and_acceptance_mention_secrets_and_both_are_dispatched_only() -> None:
    holders = {path.name for path in workflow_files() if "secrets." in path.read_text()}
    assert holders == SECRET_HOLDERS, f"the workflows that mention secrets. are {sorted(holders)}"
    for name in SECRET_HOLDERS:
        assert set(triggers(load_workflow(WORKFLOWS / name))) == {"workflow_dispatch"}, name
