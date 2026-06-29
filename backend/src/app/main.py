"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.api.routes import backtest_runs_router, data_partitions_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(title="tradebox API")
    app.include_router(backtest_runs_router)
    app.include_router(data_partitions_router)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
