"""CLI command implementations."""

from __future__ import annotations

from argparse import Namespace
from importlib.metadata import PackageNotFoundError, version

from traingluonts.cli.io import read_request_json, write_response


def run_version(args: Namespace) -> int:
    """Print package version information."""
    write_response(
        {
            "ok": True,
            "version": _package_version(),
        },
        args.output,
        pretty=args.pretty,
    )
    return 0


def run_train(args: Namespace) -> int:
    """Train a model from a request JSON file."""
    from traingluonts.trainer import train_model

    request = read_request_json(args.input)
    result = train_model(request)
    write_response(
        {
            "ok": True,
            "result": result.model_dump(mode="json"),
        },
        args.output,
        pretty=args.pretty,
    )
    return 0


def run_predict(args: Namespace) -> int:
    """Run prediction from a request JSON file."""
    from traingluonts.inference import predict

    request = read_request_json(args.input)
    result = predict(request)
    write_response(
        {
            "ok": True,
            "result": result.model_dump(mode="json"),
        },
        args.output,
        pretty=args.pretty,
    )
    return 0


def _package_version() -> str:
    try:
        return version("traingluonts")
    except PackageNotFoundError:
        return "0.1.0"

