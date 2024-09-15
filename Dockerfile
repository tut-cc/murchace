FROM almalinux:9-minimal

WORKDIR /usr/local/bin
RUN microdnf update -y \
 && curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64 \
 && chmod +x tailwindcss-linux-x64 \
 && ln -sf tailwindcss-linux-x64 tailwindcss \
 && microdnf clean all    
COPY --from=ghcr.io/astral-sh/uv:0.4.0 /uv /bin/uv
COPY . /murchace/
WORKDIR /murchace
RUN uv sync --frozen \
 && tailwindcss --minify -i app/styles.css -o static/styles.min.css

CMD ["uv", "run", "--frozen", "fastapi", "run", "app/main.py"]
