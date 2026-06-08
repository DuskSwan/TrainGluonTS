"""FastAPI exception handlers for module-specific errors."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from traingluonts.api.responses import error_response
from traingluonts.errors import (
    ModelPredictionError,
    ModelRegistryError,
    ModelTrainingError,
    PredictionRequestError,
    TrainingRequestError,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Register unified JSON error handlers."""
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(TrainingRequestError, _training_request_handler)
    app.add_exception_handler(PredictionRequestError, _prediction_request_handler)
    app.add_exception_handler(ModelRegistryError, _model_registry_handler)
    app.add_exception_handler(ModelTrainingError, _runtime_error_handler)
    app.add_exception_handler(ModelPredictionError, _runtime_error_handler)


async def _http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "ok" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail)

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(type(exc).__name__, str(detail)),
    )


async def _validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_response("RequestValidationError", str(exc)),
    )


async def _training_request_handler(
    request: Request,
    exc: TrainingRequestError,
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=error_response(type(exc).__name__, str(exc)),
    )


async def _prediction_request_handler(
    request: Request,
    exc: PredictionRequestError,
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=error_response(type(exc).__name__, str(exc)),
    )


async def _model_registry_handler(
    request: Request,
    exc: ModelRegistryError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=error_response(type(exc).__name__, str(exc)),
    )


async def _runtime_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=error_response(type(exc).__name__, str(exc)),
    )
