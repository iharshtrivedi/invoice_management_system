FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy dependency metadata first for better build caching.
COPY pyproject.toml uv.lock ./

# Install dependencies without installing the project as a package.
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source and configuration.
COPY . .

# Make the virtual environment available on PATH.
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
