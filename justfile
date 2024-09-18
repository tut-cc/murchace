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
