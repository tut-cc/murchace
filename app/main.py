from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .env import DEBUG
from .routers import placements, products, register, stat
from .store import startup_and_shutdown_db
from .templates import macro_template


# https://stackoverflow.com/a/65270864
# https://fastapi.tiangolo.com/advanced/events/
@asynccontextmanager
async def lifespan(_: FastAPI):
    startup_db, shutdown_db = startup_and_shutdown_db
    await startup_db()
    yield
    await shutdown_db()


app = FastAPI(debug=DEBUG, lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")


@macro_template("index.html")
def tmp_index(): ...


@app.get("/", response_class=HTMLResponse)
async def get_root(request: Request):
    return HTMLResponse(tmp_index(request))


app.include_router(products.router)
app.include_router(register.router)
app.include_router(placements.router)
app.include_router(stat.router)
