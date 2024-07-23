from fastapi.templating import Jinja2Templates

from .env import DEBUG

if DEBUG:
    templates = Jinja2Templates(
        directory="app/templates", extensions=["jinja2.ext.debug"]
    )
else:
    templates = Jinja2Templates(directory="app/templates")
