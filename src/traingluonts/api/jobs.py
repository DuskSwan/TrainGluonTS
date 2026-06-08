"""In-memory training job store for the HTTP API."""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from traingluonts.api.schemas import TrainJobResult
from traingluonts.api.settings import ApiSettings
from traingluonts.errors import TrainGluonTSError
from traingluonts.trainer import train_model


class TrainingJobStore:
    """A lightweight in-memory job store for first-version API usage."""

    def __init__(self) -> None:
        self._jobs: dict[str, TrainJobResult] = {}
        self._lock = Lock()

    def create(self) -> TrainJobResult:
        now = datetime.now(timezone.utc)
        job = TrainJobResult(
            job_id=uuid4().hex,
            status="queued",
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> TrainJobResult | None:
        with self._lock:
            return self._jobs.get(job_id)

    def run(self, job_id: str, request: dict, settings: ApiSettings) -> None:
        self._update(job_id, status="running")
        try:
            result = train_model(request)
        except TrainGluonTSError as exc:
            self._update(
                job_id,
                status="failed",
                error={
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            )
        except Exception as exc:
            self._update(
                job_id,
                status="failed",
                error={
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            )
        else:
            self._update(
                job_id,
                status="completed",
                result=result.model_dump(mode="json"),
            )

    def _update(
        self,
        job_id: str,
        *,
        status: str,
        result: dict | None = None,
        error: dict[str, str] | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = job.model_copy(
                update={
                    "status": status,
                    "updated_at": datetime.now(timezone.utc),
                    "result": result,
                    "error": error,
                }
            )

