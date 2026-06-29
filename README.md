# tradebox

`tradebox` is a trading research, backtesting, and market scanner platform.

The project is intentionally starting with a clean foundation: FastAPI metadata APIs, Dagster
pipeline wiring, shared-core market-data/backtesting helpers, local Postgres support, private R2
storage utilities, guarded Databento smoke ingestion, raw-to-clean Parquet conversion, and local
verification scripts.

This repository does not currently implement live trading, the real SPY strategy logic, broad
Databento ingestion, scanner workflows, or a dashboard. Backtesting support currently covers clean
Parquet loading, a no-op runner, run metadata, and persistence/API reads for detected setups and
simulated trades.

## Current architecture

- Backend app: `backend` using Python/FastAPI with package name `app`
- Pipeline app: `pipelines` using Dagster with package name `pipelines`
- Shared core package: `packages/shared_core` with package name `shared_core`
- Local database: Postgres
- Private object storage/data lake: Cloudflare R2
- Guarded market data vendor smoke path: Databento
- Raw market data format: Databento DBN
- Clean market data format: Parquet
- Future dashboard: FastAPI + React/Vite + TradingView Lightweight Charts
- Future execution integration: Schwab Trader API, not yet implemented

## Foundation data flow

The current foundation proves this small research pipeline:

1. Pull a tiny, explicitly approved market-data sample from Databento.
2. Store raw Databento DBN files in private Cloudflare R2.
3. Catalog raw data in Postgres through `data_partitions`.
4. Transform raw DBN into clean Parquet datasets.
5. Store clean Parquet datasets in private Cloudflare R2.
6. Run no-op backtests against clean Parquet.
7. Store backtest runs, detected setups, simulated trades, and metadata in Postgres.
8. Eventually expose results through a dashboard.

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
pip install -e "./packages/tradebox_workflows[dev]"
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
.venv/bin/dagster definitions validate -m pipelines.definitions
```

Run the local Dagster SPY raw-to-clean job against the existing raw R2 sample:

```bash
.venv/bin/dagster job execute -m pipelines.definitions -j spy_raw_to_clean_job
```

This job wraps `scripts/smoke_raw_to_clean_spy.py`; it does not make a Databento request. Keep
`ALLOW_LIVE_DATABENTO_REQUEST` unset or `false` for this local wrapper.

Run the guarded market-data pipeline foundation in safe existing-sample mode:

```bash
.venv/bin/dagster job execute -m pipelines.definitions -j safe_market_data_pipeline_job
```

This job materializes:

```text
market_data_request_plan -> raw_market_data_partition -> clean_market_data_partition
```

Default mode is `existing_sample`, which reads the existing raw SPY partition metadata and runs the
raw-to-clean converter. It does not make a live Databento request.

Start the Dagster UI locally:

```bash
.venv/bin/dagster dev -m pipelines.definitions --host 127.0.0.1 --port 3000
```

Then open:

```text
http://127.0.0.1:3000
```

In the UI, open the `market_data` asset group or the `safe_market_data_pipeline_job`, then launch
the job/materialization. A successful safe run should show `partition_status=validated` and
`row_count=1` in the logs/metadata.

Live Databento mode is intentionally not the default. To run it manually, first understand that it
may consume Databento credits, then set explicit environment approval:

```bash
MARKET_DATA_MODE=live_databento \
ALLOW_LIVE_DATABENTO_REQUEST=true \
.venv/bin/dagster job execute -m pipelines.definitions -j safe_market_data_pipeline_job
```

Do not use live mode for broad ranges, symbol lists, or unattended runs.

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

## Cloudflare R2 smoke test

R2 credentials are read from environment variables and should stay local. The dev bucket is private;
no public development URL is required.

Set these values in `.env`:

```text
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=tradebox-dev-market-data
R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
```

Run the live private-bucket smoke test from the repository root:

```bash
.venv/bin/python scripts/smoke_r2_connection.py
```

The smoke test writes a tiny object under `dev/smoke-tests/`, reads it back, verifies it can be
found, and deletes it.

Run the R2 plus Postgres data partition catalog smoke test from the repository root:

```bash
.venv/bin/python scripts/smoke_data_partition_r2.py
```

By default, this uploads a tiny private R2 object, computes its content hash, creates and reads a
`data_partitions` row, then deletes the temporary object and row. To keep the artifacts for manual
inspection:

```bash
.venv/bin/python scripts/smoke_data_partition_r2.py --keep-artifacts
```

Run the tiny Databento SPY-to-R2 smoke ingestion from the repository root:

```bash
.venv/bin/python scripts/smoke_databento_to_r2.py --confirm-credit-use
```

This command intentionally requires `--confirm-credit-use` because live Databento historical
requests may consume credits. The default request is one SPY `ohlcv-1m` record from a one-minute
historical window. It uploads the raw DBN sample to private R2 under
`dev/databento-smoke-tests/raw/`, creates or updates a `data_partitions` metadata row, and verifies
that row can be read back.

Run the tiny no-op SPY backtest smoke from the repository root:

```bash
.venv/bin/python scripts/smoke_noop_backtest_spy.py
```

This reads the existing clean SPY Parquet object from private R2, creates a `backtest_runs` row,
runs the placeholder no-op strategy, and records a successful zero-setup/zero-trade result. It does
not read raw market data and does not call Databento.

Verify the no-op backtest run through the backend API metadata layer:

```bash
.venv/bin/python scripts/verify_noop_backtest_api.py
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
cd ../tradebox_workflows
../../.venv/bin/python -m pytest -p no:cacheprovider
cd ../..
.venv/bin/ruff check --no-cache backend packages pipelines
```

## Notes

This project is research infrastructure first. Keep ingestion, storage, strategy, backtesting, scanning, orchestration, and dashboard responsibilities separate so each piece can evolve safely.
