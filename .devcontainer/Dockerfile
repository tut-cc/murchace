FROM almalinux:9

ENV TZ=Asia/Tokyo

WORKDIR /usr/local/bin

COPY --from=ghcr.io/astral-sh/uv:0.5.5 /uv /bin/uv

RUN dnf update -y \
    && dnf install -y git vim curl wget --allowerasing \
    && dnf clean all \
    && rm -rf /var/cache/dnf
