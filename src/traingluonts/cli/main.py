"""Executable CLI entrypoint for TrainGluonTS."""

from __future__ import annotations

import argparse
import sys
import traceback
from argparse import Namespace
from collections.abc import Sequence

from traingluonts.cli.commands import run_predict, run_train, run_version
from traingluonts.cli.io import CliInputError, write_response
from traingluonts.errors import (
    ModelPredictionError,
    ModelRegistryError,
    ModelTrainingError,
    PredictionRequestError,
    TrainingRequestError,
)


EXIT_RUNTIME_ERROR = 1
EXIT_INPUT_ERROR = 2
EXIT_TRAINING_REQUEST_ERROR = 3
EXIT_PREDICTION_REQUEST_ERROR = 4
EXIT_MODEL_REGISTRY_ERROR = 5


class CliArgumentError(Exception):
    """Raised when argparse rejects the command line."""


class JsonArgumentParser(argparse.ArgumentParser):
    """ArgumentParser variant that lets main emit JSON errors."""

    def error(self, message: str) -> None:
        raise CliArgumentError(message)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = JsonArgumentParser(prog="traingluonts")
    subparsers = parser.add_subparsers(dest="command", required=True)

    version_parser = subparsers.add_parser("version", help="print version JSON")
    _add_output_options(version_parser)
    version_parser.set_defaults(handler=run_version)

    train_parser = subparsers.add_parser("train", help="train a model")
    train_parser.add_argument("--input", required=True, help="training request JSON")
    _add_output_options(train_parser)
    train_parser.set_defaults(handler=run_train)

    predict_parser = subparsers.add_parser("predict", help="run prediction")
    predict_parser.add_argument(
        "--input",
        required=True,
        help="prediction request JSON",
    )
    _add_output_options(predict_parser)
    predict_parser.set_defaults(handler=run_predict)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the TrainGluonTS CLI."""
    args: Namespace | None = None

    try:
        args = build_parser().parse_args(argv)
        return args.handler(args)
    except CliArgumentError as exc:
        return _emit_error(exc, EXIT_INPUT_ERROR, args)
    except CliInputError as exc:
        return _emit_error(exc, EXIT_INPUT_ERROR, args)
    except TrainingRequestError as exc:
        return _emit_error(exc, EXIT_TRAINING_REQUEST_ERROR, args)
    except PredictionRequestError as exc:
        return _emit_error(exc, EXIT_PREDICTION_REQUEST_ERROR, args)
    except ModelRegistryError as exc:
        return _emit_error(exc, EXIT_MODEL_REGISTRY_ERROR, args)
    except (ModelTrainingError, ModelPredictionError) as exc:
        return _emit_error(exc, EXIT_RUNTIME_ERROR, args)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return _emit_error(exc, EXIT_RUNTIME_ERROR, args)


def _add_output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", help="write response JSON to this file")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="pretty-print response JSON",
    )


def _emit_error(
    exc: Exception,
    exit_code: int,
    args: Namespace | None,
) -> int:
    payload = {
        "ok": False,
        "error": {
            "type": type(exc).__name__,
            "message": str(exc),
        },
    }
    output = getattr(args, "output", None)
    pretty = bool(getattr(args, "pretty", False))

    try:
        write_response(payload, output, pretty=pretty)
    except Exception as write_exc:
        write_response(payload, None, pretty=pretty)
        print(f"failed to write CLI response: {write_exc}", file=sys.stderr)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

