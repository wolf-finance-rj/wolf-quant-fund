# syntax=docker/dockerfile:1

# Imagem de desenvolvimento do Wolf Quant Fund: Python 3.12 + uv,
# com as dependências fixadas pelo uv.lock.
FROM python:3.12-slim-trixie

# Binário oficial do uv para sincronizar o projeto e rodar comandos.
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1ª camada: dependências do lock (mudam pouco e ficam em cache entre builds).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --group dev --no-install-project

# 2ª camada: projeto completo (instala o pacote wqf em modo editable).
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --group dev

ENV PATH="/opt/venv/bin:$PATH"

# O container fica em repouso; comandos rodam via `docker compose run/exec`.
CMD ["sleep", "infinity"]
