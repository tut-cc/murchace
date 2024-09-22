default:
    @just --list --unsorted --justfile {{ justfile() }}

sync:
    uv sync --frozen

serve:
    uv run --frozen fastapi run app/main.py

watch:
    MURCHACE_DEBUG=1 uv run --frozen fastapi dev app/main.py

tailwind-build:
    tailwindcss --minify -i app/styles.css -o static/styles.min.css

tailwind-watch:
    tailwindcss --watch -i app/styles.css -o static/styles.css

test:
    JUST_UNSTABLE=1 just --fmt --check
    ruff check
    ruff format --diff
    uv run --frozen pyright --stats
    uv run --frozen pytest

snapshot-review:
    uv run --frozen pytest --inline-snapshot=review
