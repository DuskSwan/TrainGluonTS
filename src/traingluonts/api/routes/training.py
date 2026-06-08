"""Training routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from traingluonts.api.paths import normalize_training_request
from traingluonts.api.responses import ok_response
from traingluonts.api.schemas import TrainJobCreateRequest
from traingluonts.trainer import train_model


router = APIRouter(tags=["training"])


@router.post("/train")
def train(request: Request, payload: dict[str, Any]) -> dict:
    """Train a model synchronously."""
    settings = request.app.state.settings
    normalized = normalize_training_request(payload, settings)
    result = train_model(normalized)
    return ok_response(result.model_dump(mode="json"))


@router.post("/train/jobs")
def create_training_job(
    request: Request,
    payload: TrainJobCreateRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Create an asynchronous training job."""
    settings = request.app.state.settings
    normalized = normalize_training_request(payload.request, settings)
    job_store = request.app.state.training_jobs
    job = job_store.create()
    background_tasks.add_task(job_store.run, job.job_id, normalized, settings)
    return ok_response(job.model_dump(mode="json"))


@router.get("/train/jobs/{job_id}")
def get_training_job(request: Request, job_id: str) -> dict:
    """Return training job status."""
    job = request.app.state.training_jobs.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "ok": False,
                "error": {
                    "type": "JobNotFound",
                    "message": f"training job does not exist: {job_id}",
                },
            },
        )
    return ok_response(job.model_dump(mode="json"))

