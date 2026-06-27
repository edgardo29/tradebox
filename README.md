# tradebox

`tradebox` is a trading research, backtesting, and market scanner platform.

The project is intentionally starting with a clean foundation: FastAPI backend package structure, Dagster pipeline placeholders, shared-core package scaffolding, local Postgres support, environment-based configuration, and documentation for future Codex/agent work.

This repository does not currently implement live trading, strategy logic, Databento ingestion, Cloudflare R2 storage, or a dashboard.

## Current architecture

- Backend app: `backend` using Python/FastAPI with package name `app`
- Pipeline app: `pipelines` using Dagster with package name `pipelines`
- Shared core package: `packages/shared_core` with package name `shared_core`
- Local database: Postgres
- Future object storage/data lake: Cloudflare R2
- Future market data vendor: Databento
- Future raw market data format: Databento DBN
- Future clean market data format: Parquet
- Future dashboard: FastAPI + React/Vite + TradingView Lightweight Charts
- Future execution integration: Schwab Trader API, not yet implemented

## Planned data flow

The intended research pipeline is:

1. Pull market data from Databento.
2. Store raw Databento DBN files in Cloudflare R2.
3. Transform raw DBN into clean Parquet datasets.
4. Store clean Parquet datasets in Cloudflare R2.
5. Run scanners and backtests against clean Parquet.
6. Store backtest/scanner results and metadata in Postgres.
7. Eventually expose results through a dashboard.

## Local development

This project uses native local PostgreSQL for development.

Copy the example environment file before running local services:

```bash
cp .env.example .env
```

The backend expects an existing local Postgres server at:

```text
localhost:5432
```

Create a separate local database named:

```text
tradebox_db_dev
```

The backend reads the database connection from `DATABASE_URL`:

```text
postgresql+psycopg://<user>:<password>@localhost:5432/tradebox_db_dev
```

If the local role or database does not exist yet, create them with your local Postgres admin
user. Replace `YOUR_POSTGRES_PASSWORD` with a local development password:

```bash
psql -h localhost -p 5432 -U postgres -d postgres -c "CREATE ROLE tradebox_user WITH LOGIN PASSWORD 'YOUR_POSTGRES_PASSWORD';"
createdb -h localhost -p 5432 -U postgres -O tradebox_user tradebox_db_dev
```

If the role already exists, only create the database:

```bash
createdb -h localhost -p 5432 -U postgres -O tradebox_user tradebox_db_dev
```

## Backend development

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e "./backend[dev]"
pip install -e "./pipelines[dev]"
pip install -e "./packages/shared_core[dev]"
```

Run backend tests:

```bash
cd backend
../.venv/bin/python -m pytest -p no:cacheprovider
```

Run Alembic from `backend/`:

```bash
cd backend
../.venv/bin/python -m alembic current
../.venv/bin/python -m alembic upgrade head
```

During early local development, the schema is rebuildable. This drops and recreates the local
development schema records managed by Alembic:

```bash
cd backend
../.venv/bin/python -m alembic downgrade base
../.venv/bin/python -m alembic upgrade head
```

Start the FastAPI backend locally:

```bash
cd backend
../.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Confirm the health endpoint from another shell:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## Pipeline development

From the repository root:

```bash
cd pipelines
../.venv/bin/python -m pytest -p no:cacheprovider
```

From the repository root, confirm the Dagster definitions object imports:

```bash
.venv/bin/python -c "from pipelines.definitions import defs; print(type(defs).__name__)"
```

## Shared core development

From the repository root:

```bash
cd packages/shared_core
../../.venv/bin/python -m pytest -p no:cacheprovider
```

From the repository root, confirm the shared package imports:

```bash
.venv/bin/python -c "import shared_core; print(shared_core.__version__)"
```

Run compileall from the repository root:

```bash
.venv/bin/python -m compileall backend pipelines packages
```

Run Ruff from the repository root:

```bash
.venv/bin/ruff check --no-cache backend packages pipelines
```

Run all current validation from the repository root:

```bash
.venv/bin/python -m compileall backend pipelines packages
cd backend
../.venv/bin/python -m pytest -p no:cacheprovider
../.venv/bin/python -m alembic upgrade head
cd ../pipelines
../.venv/bin/python -m pytest -p no:cacheprovider
cd ../packages/shared_core
../../.venv/bin/python -m pytest -p no:cacheprovider
cd ../..
.venv/bin/ruff check --no-cache backend packages pipelines
```

## Notes

This project is research infrastructure first. Keep ingestion, storage, strategy, backtesting, scanning, orchestration, and dashboard responsibilities separate so each piece can evolve safely.
