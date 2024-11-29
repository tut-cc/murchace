# This file defines types for doit objects. If type errors are found, we should
# modify this module according to the implementation details.

from os import PathLike
from typing import Any, Callable, Generator, Literal, Sequence, TypedDict

from doit.action import BaseAction
from doit.exceptions import BaseFail

type Action = (
    str
    | PathLike
    | Sequence[str | PathLike]
    | BaseAction
    | Callable[..., str | Sequence[str | PathLike] | BaseFail | None]
)


class ParamBase(TypedDict):
    name: str
    """variable name"""
    default: str
    """default value (from its type)"""


class Param(ParamBase, total=False):
    section: str
    """meta info used to group entries when generating help"""
    type: type
    """
    type of the variable. must be able to be initialized
    taking a single string parameter.
    if type is bool. option is just a flag. and if present
    its value is set to True.
    """
    short: str
    """argument short name"""
    long: str
    """argument long name"""
    inverse: str
    """
    argument long name to be the inverse of the default
    value (only used by boolean options)
    """
    choices: list[tuple[str, str]]
    """sequence of 2-tuple of choice name, choice description."""
    help: str
    """option description"""
    # metavar: str
    # env_var: str


class TaskBase(TypedDict):
    actions: list[Action] | tuple[Action] | None  # list - L{BaseAction}


# See doit.task.Task object for reference
class TaskDict(TaskBase, total=False):
    basename: str
    name: str
    file_dep: Sequence[str | PathLike]  # list, tuple (set - string)
    task_dep: Sequence[str]  # list, tuple
    uptodate: (
        list[bool | Callable[..., bool]] | tuple[bool | Callable[..., bool]]
    )  # (list - bool/None)
    """use bool/computed value instead of checking dependencies"""
    # calc_dep: list | tuple
    # """reference to a task"""
    targets: list[str | PathLike] | tuple[str | PathLike]  # (list - string)
    # setup: list | tuple
    # clean: list | tuple | Literal[True]
    # teardown: list | tuple - L{BaseAction}
    # doc: str | None
    # """task documentation"""
    params: list[Param] | tuple[Param]
    pos_arg: str | None
    """name of parameter in action to receive positional parameters from command line"""
    verbosity: None | Literal[0] | Literal[1] | Literal[2]
    # io: dict | None
    # getargs: dict
    # """values from other tasks"""
    # title: Callable | None
    # watch: list | tuple
    # meta: dict | None
    # """extra info from user/plugin not directly used by doit"""


type TaskDictGen = _Gen[TaskDict]
type _Gen[T] = Generator[T, Any, None]
