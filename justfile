export TAILWINDCSS_VERSION := 'v3.4.13'

alias r := run
alias w := watch
alias tb := tailwind-build
alias tw := tailwind-watch
alias t := test
alias sr := snapshot-review

# List just recipes.
default:
    @just --list --unsorted --no-aliases --justfile {{ justfile() }}

# Start the web server.
run:
    uv run --frozen fastapi run app/main.py

# DEPRECATED. Use `run` instead.
serve:
    @echo 'WARNING: `just serve` is deprecated. Run `just run` instead.'
    @echo '変更理由: アプリケーションの実行は "run" のほうがよく使われているため。'
    @echo 'WARNING: Running `just run` for now...'
    @just run

# Setup development environment.
dev:
    uv sync --frozen
    # TODO: abort the installation when the binary is already installed
    uv run --frozen tailwindcss_install

# DEPRECATED. Use `dev` instead.
sync:
    @echo 'WARNING: `just sync` is deprecated. Run `just dev` instead.'
    @echo '変更理由: uv 特有の "sync" より "dev" のほうがより一般的で開発環境を構築することが推測しやすいため。'
    @echo 'WARNING: Running `just dev` for now...'
    @just dev

# Start the dev server every time Python files change.
watch *args:
    MURCHACE_DEBUG=1 uv run --frozen fastapi dev app/main.py {{ args }}

# Generate `styles.min.css`.
tailwind-build:
    uv run --frozen tailwindcss --minify -i app/styles.css -o static/styles.min.css

# Generate `styles.css` every time template files change.
tailwind-watch:
    uv run --frozen tailwindcss --watch -i app/styles.css -o static/styles.css

# Run various tests.
test:
    #!/usr/bin/env bash
    set -eux +o pipefail # Explicitly ignore pipeline failures.

    # Check if justfile is formatted properly
    JUST_UNSTABLE=1 just --fmt --check

    # Test Python files
    uv run --frozen ruff check --ignore F821
    uv run --frozen ruff format --diff
    uv run --frozen pyright --stats
    uv run --frozen pytest

    # Lint Jinja template files
    # uv run --frozen djlint app/templates

    # Compare tailwindcss outputs
    tmp=output
    uv run --frozen tailwindcss -i app/styles.css -o "$tmp" || ( rm "$tmp" && exit 1 )
    diff "$tmp" static/styles.css || ( rm "$tmp" && exit 1 )
    rm "$tmp"
    uv run --frozen tailwindcss --minify -i app/styles.css -o "$tmp" || ( rm "$tmp" && exit 1 )
    diff "$tmp" static/styles.min.css || ( rm "$tmp" && exit 1 )
    rm "$tmp"

# Review inline snapshot tests.
snapshot-review *files_or_dirs:
    uv run --frozen pytest --inline-snapshot=review {{ files_or_dirs }}
