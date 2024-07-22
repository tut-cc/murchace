FROM almalinux:9

WORKDIR /usr/local/bin
ENV RYE_HOME="/opt/rye"
ENV PATH="$RYE_HOME/shims:$PATH"

RUN dnf update -y \
    && dnf install -y git vim curl wget --allowerasing \
    && dnf clean all \
    && rm -rf /var/cache/dnf \
    && curl -sSf https://rye.astral.sh/get | RYE_INSTALL_OPTION="--yes" bash \
    && echo 'source "$HOME/.rye/env"' >> ~/.profile \
    && echo 'source "$HOME/.rye/env"' >> ~/.bashrc \
    && mkdir -p ~/.local/share/bash-completion/completions \
    && rye self completion > ~/.local/share/bash-completion/completions/rye.bash \
    && curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64 \
    && chmod +x tailwindcss-linux-x64 \
    && ln -sf tailwindcss-linux-x64 tailwindcss
    