# Invoice Management System

An asynchronous invoice management API built with FastAPI, SQLAlchemy, PostgreSQL, Redis, and Celery. It supports authentication, companies, customers, taxes, invoices, PDF generation, email delivery, and payment webhooks.

## Features

- JWT-based authentication and password reset flows
- Company-scoped customers, taxes, invoices, and users
- Invoice lifecycle management: draft, confirmed, and cancelled
- Invoice line items with tax calculations
- Downloadable invoice PDFs
- Asynchronous invoice email delivery with Celery and Redis
- Invoice email delivery status tracking
- Payment webhook processing and rate limiting
- Database migrations with Alembic
- Interactive OpenAPI documentation through FastAPI

## Requirements

- Python 3.14 or newer
- PostgreSQL
- Redis
- [uv](https://docs.astral.sh/uv/)

The application reads settings from the environment file configured in `config.py`. At minimum, configure `DATABASE_URL`, `SECRET_KEY`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, and `REDIS_URL`. Mail and webhook settings are also available in `config.py`.

## Run locally

1. Create or update the environment file expected by `config.py`:

   `C:\fastapi\secrets\invoice_management_system.env`

2. Install dependencies:

   ```powershell
   uv sync
   ```

3. Apply database migrations:

   ```powershell
   uv run alembic upgrade head
   ```

4. Start the API:

   ```powershell
   uv run uvicorn main:app --reload
   ```

5. Open [http://localhost:8000/](http://localhost:8000/). The home route redirects to the Swagger UI at `/docs`. ReDoc is available at `/redoc`, and the health check is available at `/health`.

For background email tasks, run the Celery worker in a separate terminal:

```powershell
uv run celery -A services.celery_app:celery_app worker --loglevel=info
```

Run Celery Beat as well when scheduled tasks are needed:

```powershell
uv run celery -A services.celery_app:celery_app beat --loglevel=info
```

## Run with Docker Compose

The Compose setup starts the API, Redis, Celery worker, and Celery Beat:

```powershell
docker compose up --build
```

The API is then available at [http://localhost:8000/](http://localhost:8000/). Ensure the environment file referenced by `compose.yaml` exists, or update that path for your environment.

## Run tests

```powershell
uv run pytest
```

The test suite is configured in `pyproject.toml` and uses the `tests/` directory.

## API route groups

| Prefix | Purpose |
| --- | --- |
| `/api/auth` | Registration, login, and password reset |
| `/api/users` | User management |
| `/api/customers` | Customer management |
| `/api/taxes` | Tax management |
| `/api/invoices` | Invoice and invoice-line management |
| `/api/services` | Invoice confirmation, cancellation, PDFs, and email delivery |
| `/api/webhooks` | Payment webhook handling |

Use the Swagger UI at `/docs` to inspect request schemas and try the endpoints.
