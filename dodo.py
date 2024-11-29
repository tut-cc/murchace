# https://pydoit.org/tasks.html
# from doit import cmd_list

# # Tab Completion
#
# For Bash:
#
# ```
# doit tabcompletion --shell bash > doit_comp.sh
# source doit_comp.sh
# ```
#
# For ZSH:
#
# ```
# doit tabcompletion --shell zsh > ~/.local/share/zsh/zfunc/_doit
# ```

from doit.action import TaskFailed
from doit.tools import Interactive, LongRunning

from tasks.tailwindcss import (  # noqa: F401
    task__tailwind_install,
    task_tailwind_build,
    task_tailwind_watch,
)
from tasks.task_dict import TaskDict, TaskDictGen

DOIT_CONFIG = {
    "default_tasks": ["_list"],
    "action_string_formatting": "new",
}

UV_RUN = ["uv", "run", "--frozen"]


def task__list() -> TaskDict:
    cmd = ["doit", "list", "--all", "--status", "--sort=definition"]
    return {"actions": [cmd], "verbosity": 2}


def task_serve() -> TaskDictGen:
    """Start the prod server."""
    cmd = LongRunning([*UV_RUN, "fastapi", "run", "app/main.py"], shell=False)
    yield {"basename": "serve", "actions": [cmd], "verbosity": 2}
    yield {"basename": "s", "actions": [cmd], "verbosity": 2}


def task_dev() -> TaskDict:
    """Setup development environment."""
    return {"actions": None, "task_dep": ["_uv_sync", "_tailwind_install"]}


def task__uv_sync() -> TaskDict:
    cmd = ["uv", "sync", "--frozen"]
    return {"file_dep": ["pyproject.toml"], "actions": [cmd], "targets": ["uv.lock"]}


def task_watch() -> TaskDictGen:
    """Start the dev server every time Python files change."""

    def cmd(args: list[str]) -> None:
        cmd_action = LongRunning(
            [*UV_RUN, "fastapi", "dev", "app/main.py", *args],
            shell=False,
            env={"MURCHACE_DEBUG": "1"},
        )
        cmd_action.execute()

    yield {"basename": "watch", "actions": [cmd], "pos_arg": "args", "verbosity": 2}
    yield {"basename": "w", "actions": [cmd], "pos_arg": "args", "verbosity": 2}


def task_test() -> TaskDictGen:
    """Run various tests."""

    from tasks import tailwindcss

    actions = [
        [*UV_RUN, "ruff", "check"],
        [*UV_RUN, "ruff", "format", "--diff"],
        [*UV_RUN, "pyright", "--stats"],
        [*UV_RUN, "pytest"],
        # Lint Jinja template files
        # [*UV_RUN, "djlint", "app/templates", "--ignore", "H006,H030,H031"]
        tailwindcss.comparison_test,
    ]
    yield {"basename": "test", "actions": actions, "verbosity": 2}
    yield {"basename": "t", "actions": actions, "verbosity": 2}


def task_snapshot_review() -> TaskDictGen:
    """Review inline snapshot tests."""

    def cmd(files_or_dirs: list[str]) -> TaskFailed | None:
        cmd_action = Interactive(
            [*UV_RUN, "pytest", "--inline-snapshot=review", *files_or_dirs], shell=False
        )
        return cmd_action.execute()

    task: TaskDict = {"actions": [cmd], "pos_arg": "files_or_dirs", "verbosity": 2}
    yield {"basename": "snapshot-review", **task}
    yield {"basename": "sr", **task}
