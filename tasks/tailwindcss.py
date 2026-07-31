# Installing/running tailwindcss binary

import os
from collections.abc import Generator
from pathlib import Path

from doit.action import PythonAction, TaskFailed
from doit.tools import LongRunning, config_changed

from .task_dict import TaskDict

# Manually update the version string.
# List of available tailwindcss versions are here:
# https://github.com/tailwindlabs/tailwindcss/releases
# Setting it to "latest" will lead to an unreproducible build.
VERSION = os.environ.get("TAILWINDCSS_VERSION", "v4.3.3")
BINARY_PATH = Path(__file__).parent.resolve() / "bin" / f"tailwindcss-{VERSION}"
BINARY_SYMLINK_PATH = BINARY_PATH.parent / "tailwindcss"


def task__tailwind_install() -> TaskDict:
    return {
        "actions": [install_binary],
        "targets": [BINARY_PATH],
        "uptodate": [config_changed(VERSION)],
    }


TAILWIND_INPUT = Path("app/input.css")
assert TAILWIND_INPUT.exists()
CMD_FMT = [BINARY_PATH, "--optimize", "-i", TAILWIND_INPUT]
CMD_MIN = CMD_FMT + ["--minify"]


def task_tailwind_build() -> Generator[TaskDict, None, TaskFailed | None]:
    """Generate `styles.min.css`."""
    if not BINARY_PATH.exists():
        return TaskFailed(f"{BINARY_PATH} does not exist; run `doit dev` first")
    CSS_MIN = Path("static/styles.min.css")
    # NOTE: unfortunately as of v4.1.14, tailwindcss produces different
    # results on the first invocation and the subsequent invocations, so
    # we remove the min file before the build to mimic reproducibility
    # TODO: find the issue related to reproducibility or file one
    rm_file = PythonAction(lambda: CSS_MIN.unlink(missing_ok=True))
    cmds = [rm_file, CMD_MIN + ["-o", CSS_MIN]]

    # TODO: Figure out a way to assign the same target to two tasks.
    # The issue arrises because using `"targets": ["static/styles.min.css"]`
    # more than twice for different basename tasks is disallowed. It would be
    # ideal if we could somehow get around that limitation.
    yield {"basename": "tailwind-build", "actions": cmds}
    yield {"basename": "tb", "actions": cmds}


def task_tailwind_watch() -> Generator[TaskDict, None, TaskFailed | None]:
    """Generate `styles.css` every time files change."""
    if not BINARY_PATH.exists():
        return TaskFailed(f"{BINARY_PATH} does not exist; run `doit dev` first")
    cmd = LongRunning(CMD_FMT + ["-w", "-o", "static/styles.css"], shell=False)
    yield {"basename": "tailwind-watch", "actions": [cmd]}
    yield {"basename": "tw", "actions": [cmd]}


def task__tailwind_test() -> TaskDict:
    """Compare tailwindcss outputs."""
    return {"file_dep": [BINARY_PATH], "actions": [comparison_test]}


def install_binary() -> None:
    import stat
    import urllib.request
    from urllib.error import HTTPError

    BINARY_PATH.parent.mkdir(exist_ok=True)
    BINARY_PATH.unlink(missing_ok=True)
    BINARY_SYMLINK_PATH.unlink(missing_ok=True)

    url = get_download_url(VERSION)
    print(f"Downloading from '{url}'...")
    try:
        urllib.request.urlretrieve(url, BINARY_PATH)
    except HTTPError as err:
        if err.code == 404:
            raise RuntimeError(
                f"Couldn't find Tailwind CSS binary for version {VERSION}. "
                f"Please check if this version exists at "
                f"https://github.com/tailwindlabs/tailwindcss/releases"
            )
        raise

    BINARY_PATH.chmod(BINARY_PATH.stat().st_mode | stat.S_IEXEC)  # Set executable bit
    BINARY_SYMLINK_PATH.symlink_to(BINARY_PATH.name)


def get_download_url(version: str) -> str:
    import platform

    os_name_by_uname = platform.system().lower()
    os_name = os_name_by_uname.replace("win32", "windows").replace("darwin", "macos")
    assert os_name in ["linux", "windows", "macos"]
    extension = ".exe" if os_name == "windows" else ""

    target = {
        "amd64": f"{os_name}-x64{extension}",
        "x86_64": f"{os_name}-x64{extension}",
        "arm64": f"{os_name}-arm64",
        "aarch64": f"{os_name}-arm64",
    }.get(platform.machine().lower())
    if target is None:
        raise RuntimeError(f"{platform.machine()} architecture is not supported")
    binary_name = f"tailwindcss-{target}"

    if version == "latest":
        return f"https://github.com/tailwindlabs/tailwindcss/releases/latest/download/{binary_name}"
    return f"https://github.com/tailwindlabs/tailwindcss/releases/download/{version}/{binary_name}"


def comparison_test() -> TaskFailed | None:
    import subprocess

    tmpfile = Path("output")
    try:
        print(str(" ".join(str(arg) for arg in CMD_FMT + ["-o", tmpfile])))
        subprocess.run(CMD_FMT + ["-o", tmpfile], check=True)
        subprocess.run(
            ["diff", "--color=always", "static/styles.css", tmpfile], check=True
        )
        tmpfile.unlink()
        print(str(" ".join(str(arg) for arg in CMD_MIN + ["-o", tmpfile])))
        subprocess.run(CMD_MIN + ["-o", tmpfile], check=True)
        subprocess.run(
            ["diff", "--color=always", "static/styles.min.css", tmpfile], check=True
        )
    except subprocess.CalledProcessError as e:
        tmpfile.unlink(missing_ok=True)
        return TaskFailed(e)
    tmpfile.unlink()
