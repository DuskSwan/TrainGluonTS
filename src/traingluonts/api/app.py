"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from traingluonts.api.errors import register_exception_handlers
from traingluonts.api.jobs import TrainingJobStore
from traingluonts.api.routes import health, models, prediction, training
from traingluonts.api.settings import ApiSettings, load_settings


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    """Create and configure the TrainGluonTS FastAPI app."""
    resolved_settings = settings or load_settings()
    app = FastAPI(
        title="TrainGluonTS API",
        version="0.1.0",
    )

    app.state.settings = resolved_settings
    app.state.training_jobs = TrainingJobStore()

    if resolved_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved_settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_exception_handlers(app)
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(training.router, prefix="/api/v1")
    app.include_router(prediction.router, prefix="/api/v1")
    app.include_router(models.router, prefix="/api/v1")
    return app


app = create_app()

