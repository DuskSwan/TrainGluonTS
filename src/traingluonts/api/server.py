"""Uvicorn entrypoint for the TrainGluonTS API."""

from __future__ import annotations

import uvicorn

from traingluonts.api.settings import load_settings


def main() -> None:
    """Run the API service with uvicorn."""
    settings = load_settings()
    uvicorn.run(
        "traingluonts.api.app:create_app",
        host=settings.host,
        port=settings.port,
        factory=True,
    )


if __name__ == "__main__":
    main()

