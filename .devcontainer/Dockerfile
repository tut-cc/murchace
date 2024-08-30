FROM almalinux:9

WORKDIR /usr/local/bin

COPY --from=ghcr.io/astral-sh/uv:0.4.0 /uv /bin/uv

RUN dnf update -y \
    && dnf install -y git vim curl wget --allowerasing \
    && curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to /usr/bin/ \
    && dnf clean all \
    && rm -rf /var/cache/dnf \
    && curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64 \
    && chmod +x tailwindcss-linux-x64 \
    && ln -sf tailwindcss-linux-x64 tailwindcss
