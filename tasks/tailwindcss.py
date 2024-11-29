# Installing/running tailwindcss binary

import os
from pathlib import Path

from doit.action import TaskFailed
from doit.tools import LongRunning, config_changed

from .task_dict import TaskDict, TaskDictGen

# List of available tailwindcss versions:
# https://github.com/tailwindlabs/tailwindcss/releases
# Or set "latest" to get the most up-to-date stable release
VERSION = os.environ.get("TAILWINDCSS_VERSION", "v3.4.13")
BINARY_PATH = Path(__file__).parent.resolve() / "bin" / f"tailwindcss-{VERSION}"
BINARY_SYMLINK_PATH = BINARY_PATH.parent / "tailwindcss"


def task__tailwind_install() -> TaskDict:
    return {
        "actions": [install_binary],
        "targets": [BINARY_PATH],
        "uptodate": [config_changed(VERSION)],
        "verbosity": 2,
    }


TAILWIND_INPUT = Path("app/styles.css")


def task_tailwind_build() -> TaskDictGen:
    """Generate `styles.min.css`."""
    template_files = Path("app/templates").glob("**/*.html")
    file_dep = [BINARY_PATH, Path("tailwind.config.js"), TAILWIND_INPUT]
    file_dep.extend(template_files)
    output = "static/styles.min.css"
    cmd = [BINARY_PATH, "--minify", "-i", TAILWIND_INPUT, "-o", output]
    task: TaskDict = {"file_dep": file_dep, "actions": [cmd], "verbosity": 2}
    # TODO: Figure out a way to assign the same target to two tasks.
    # The issue arrises because using `"targets": ["static/styles.min.css"]`
    # more than twice for different basename tasks is disallowed. It would be
    # ideal if we could somehow get around that limitation.
    yield {"basename": "tailwind-build", **task}
    yield {"basename": "tb", **task}


def task_tailwind_watch() -> TaskDictGen:
    """Generate `styles.css` every time template files change."""
    output = "static/styles.css"
    cmd = LongRunning(
        [BINARY_PATH, "--watch", "-i", TAILWIND_INPUT, "-o", output], shell=False
    )
    yield {"basename": "tailwind-watch", "actions": [cmd], "verbosity": 2}
    yield {"basename": "tw", "actions": [cmd], "verbosity": 2}


def task__tailwind_test() -> TaskDict:
    """Compare tailwindcss outputs."""
    return {"file_dep": [BINARY_PATH], "actions": [comparison_test]}


def install_binary() -> None:
    import stat
    import urllib.request
    from urllib.error import HTTPError

    os.makedirs(BINARY_PATH.parent, exist_ok=True)
    BINARY_PATH.unlink(missing_ok=True)
    BINARY_SYMLINK_PATH.unlink(missing_ok=True)

    url = get_download_url(VERSION)
    print(f"Downloading from '{url}'...")
    try:
        urllib.request.urlretrieve(url, BINARY_PATH)
    except HTTPError as err:
        if err.code == 404:
            raise Exception(
                f"Couldn't find Tailwind CSS binary for version {VERSION}. "
                f"Please check if this version exists at "
                f"https://github.com/tailwindlabs/tailwindcss/releases."
            )
        raise err

    BINARY_PATH.chmod(BINARY_PATH.stat().st_mode | stat.S_IEXEC)  # Set executable bit
    BINARY_SYMLINK_PATH.symlink_to(BINARY_PATH.relative_to(BINARY_PATH.parent))


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
        raise Exception(f"{platform.machine()} architecture is not supported")
    binary_name = f"tailwindcss-{target}"

    if version == "latest":
        return f"https://github.com/tailwindlabs/tailwindcss/releases/latest/download/{binary_name}"
    return f"https://github.com/tailwindlabs/tailwindcss/releases/download/{version}/{binary_name}"


def comparison_test() -> TaskFailed | None:
    import subprocess

    tmpfile = Path("output")
    try:
        subprocess.run([BINARY_PATH, "-i", TAILWIND_INPUT, "-o", tmpfile], check=True)
        subprocess.run(["diff", "static/styles.css", tmpfile], check=True)
        subprocess.run(
            [BINARY_PATH, "--minify", "-i", TAILWIND_INPUT, "-o", tmpfile],
            check=True,
        )
        subprocess.run(["diff", "static/styles.min.css", tmpfile], check=True)
    except subprocess.CalledProcessError:
        subprocess.run(["rm", tmpfile], check=True)
        # TODO: come up with a sensible error msg
        return TaskFailed("")
    finally:
        subprocess.run(["rm", tmpfile], check=True)
