from typing import Any
from fastapi import Request
from fastapi.templating import Jinja2Templates

from .env import DEBUG


def debug_context(_: Request) -> dict[str, Any]:
    return {"DEBUG": DEBUG}


if DEBUG:
    templates = Jinja2Templates(
        directory="app/templates",
        context_processors=[debug_context],
        extensions=["jinja2.ext.debug"],
    )
else:
    templates = Jinja2Templates(
        directory="app/templates", context_processors=[debug_context]
    )
