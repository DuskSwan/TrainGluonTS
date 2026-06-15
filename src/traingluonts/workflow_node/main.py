"""Executable ZeroMQ entrypoint for workflow-node inference."""

from __future__ import annotations

import argparse
import json
import sys
from argparse import Namespace
from collections.abc import Sequence
from multiprocessing import freeze_support

import zmq

from traingluonts.workflow_node.payloads import DEFAULT_START_TIME
from traingluonts.workflow_node.service import (
    WorkflowNodeConfig,
    WorkflowPredictionService,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the workflow-node argument parser."""
    parser = argparse.ArgumentParser(prog="traingluonts-workflow-node")
    parser.add_argument("--zmq-endpoint", required=True)
    parser.add_argument("--zmq-protocol", default="REQ")
    parser.add_argument("--model-path", required=True)
    parser.add_argument(
        "--target_name",
        "--target-name",
        dest="target_name",
        required=True,
    )
    parser.add_argument("--timestamp_name", "--timestamp-name", dest="timestamp_name")
    parser.add_argument(
        "--start_time",
        "--start-time",
        dest="start_time",
        default=DEFAULT_START_TIME,
    )
    parser.add_argument("--item_id_name", "--item-id-name", dest="item_id_name")
    parser.add_argument("--freq")
    parser.add_argument(
        "--num_samples",
        "--num-samples",
        dest="num_samples",
        type=_positive_int,
        default=100,
    )
    parser.add_argument(
        "--output_name",
        "--output-name",
        dest="output_name",
        default="predict_value",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the workflow-node ZeroMQ REP server."""
    try:
        args = build_parser().parse_args(argv)
        config = config_from_args(args)
        service = WorkflowPredictionService.from_config(config)
    except Exception as exc:
        print(f"failed to start workflow node: {exc}", file=sys.stderr)
        return 1

    return serve_forever(args.zmq_endpoint, service)


def config_from_args(args: Namespace) -> WorkflowNodeConfig:
    """Build a workflow-node config from parsed arguments."""
    protocol = str(args.zmq_protocol).upper()
    if protocol != "REQ":
        raise ValueError("only --zmq-protocol REQ is supported")

    return WorkflowNodeConfig(
        model_path=args.model_path,
        target_name=args.target_name,
        timestamp_name=args.timestamp_name,
        item_id_name=args.item_id_name,
        freq=args.freq,
        start_time=args.start_time,
        num_samples=args.num_samples,
        output_name=args.output_name,
    )


def serve_forever(
    endpoint: str,
    service: WorkflowPredictionService,
    *,
    max_requests: int | None = None,
    context: zmq.Context | None = None,
) -> int:
    """Serve workflow-node requests over a ZeroMQ REP socket."""
    owns_context = context is None
    context = context or zmq.Context()
    socket = context.socket(zmq.REP)

    try:
        socket.bind(endpoint)
        print(f"bind={endpoint}", flush=True)
        if service.predictor_path is not None:
            print(f"model_path={service.predictor_path}", flush=True)
        print(f"freq={service.freq}", flush=True)

        handled = 0
        while max_requests is None or handled < max_requests:
            text = socket.recv_string()
            response = service.process_text(text)
            socket.send_string(json.dumps(response, ensure_ascii=False, default=str))
            handled += 1
    except KeyboardInterrupt:
        return 0
    finally:
        socket.close(linger=0)
        if owns_context:
            context.term()

    return 0


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


if __name__ == "__main__":
    freeze_support()
    raise SystemExit(main())
