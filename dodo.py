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

import os
from collections.abc import Generator

from doit.action import TaskFailed
from doit.tools import Interactive, LongRunning

from tasks.tailwindcss import (  # noqa: F401
    task__tailwind_install,
    task_tailwind_build,
    task_tailwind_watch,
)
from tasks.task_dict import TaskDict

DOIT_CONFIG = {
    "default_tasks": ["_list"],
    "action_string_formatting": "new",
    "verbosity": 2,
}

UV_RUN = ["uv", "run", "--frozen"]

UVICORN_CMD = [
    *UV_RUN,
    *["uvicorn", "--port", "8000", "--workers", "4", "app.main:app"],
]


def task__list() -> TaskDict:
    cmd = [*UV_RUN, "doit", "list", "--all", "--status", "--sort=definition"]
    return {"actions": [cmd]}


def task_serve() -> Generator[TaskDict]:
    """Start the prod server."""
    cmd = LongRunning([*UVICORN_CMD, "--host", "0.0.0.0"], shell=False)
    yield {"basename": "serve", "actions": [cmd]}
    yield {"basename": "s", "actions": [cmd]}


def task_dev() -> TaskDict:
    """Setup development environment."""

    return {"actions": None, "task_dep": ["_uv_sync", "_tailwind_install"]}


def task__uv_sync() -> TaskDict:
    cmd = ["uv", "sync", "--frozen"]
    return {"file_dep": ["pyproject.toml"], "actions": [cmd], "targets": ["uv.lock"]}


def task_watch() -> Generator[TaskDict]:
    """Start the dev server every time Python files change."""

    def cmd(args: list[str]) -> None:
        action = [*UVICORN_CMD, "--host", "localhost", "--reload", *args]
        env = os.environ.copy()
        env["MURCHACE_DEBUG"] = "1"
        LongRunning(action, shell=False, env=env).execute()

    yield {"basename": "watch", "actions": [cmd], "pos_arg": "args"}
    yield {"basename": "w", "actions": [cmd], "pos_arg": "args"}


def task_test() -> Generator[TaskDict]:
    """Run various tests."""

    from tasks import tailwindcss

    actions = [
        [*UV_RUN, "ruff", "--color", "always", "check"],
        [*UV_RUN, "ruff", "--color", "always", "format", "--diff"],
        [*UV_RUN, "ty", "check", "--color", "always"],
        [*UV_RUN, "pytest", "--color", "yes"],
        tailwindcss.comparison_test,
    ]
    yield {"basename": "test", "actions": actions}
    yield {"basename": "t", "actions": actions}


def task_snapshot_review() -> Generator[TaskDict]:
    """Review inline snapshot tests."""

    def cmd(files_or_dirs: list[str]) -> TaskFailed | None:
        cmd_action = Interactive(
            [*UV_RUN, "pytest", "--inline-snapshot=review", *files_or_dirs], shell=False
        )
        return cmd_action.execute()

    yield {"basename": "snapshot-review", "actions": [cmd], "pos_arg": "files_or_dirs"}
    yield {"basename": "sr", "actions": [cmd], "pos_arg": "files_or_dirs"}
