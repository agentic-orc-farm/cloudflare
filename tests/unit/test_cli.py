from cf_plane.cli import COMMANDS, main


def test_the_command_runs_with_no_arguments() -> None:
    assert main([]) == 0


def test_command_names_are_unique() -> None:
    names = [command.name for command in COMMANDS]
    assert len(names) == len(set(names))
