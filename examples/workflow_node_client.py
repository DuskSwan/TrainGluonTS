from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a JSON request to traingluonts-workflow-node over ZeroMQ REQ."
    )
    parser.add_argument(
        "--endpoint",
        default="tcp://127.0.0.1:55555",
        help="ZeroMQ endpoint exposed by the workflow node.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Request JSON file. If omitted, a sample payload is generated.",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=30000,
        help="Send/receive timeout in milliseconds.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Send the same request this many times.",
    )
    parser.add_argument(
        "--target-name",
        default="RF_FWD_PWR",
        help="Target field name used in the generated sample payload.",
    )
    parser.add_argument(
        "--timestamp-name",
        default="time",
        help="Timestamp field name used in the generated sample payload.",
    )
    parser.add_argument(
        "--item-id-name",
        default=None,
        help="Optional item id field name used in the generated sample payload.",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=120,
        help="Number of rows generated when --input is omitted.",
    )
    parser.add_argument(
        "--freq-ms",
        type=int,
        default=30,
        help="Timestamp interval in milliseconds for the generated sample payload.",
    )
    return parser.parse_args()


def load_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"failed to read input file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"input file is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise SystemExit("input JSON must be an object")
    return payload


def make_sample_payload(
    *,
    target_name: str,
    timestamp_name: str,
    item_id_name: str | None,
    rows: int,
    freq_ms: int,
) -> dict[str, Any]:
    if rows <= 0:
        raise SystemExit("--rows must be greater than 0")
    if freq_ms <= 0:
        raise SystemExit("--freq-ms must be greater than 0")

    start = datetime(2026, 5, 25, 8, 24, 0)
    data: list[dict[str, Any]] = []

    for index in range(rows):
        timestamp = start + timedelta(milliseconds=freq_ms * index)
        value = 448.0 + math.sin(index / 8.0) * 3.0 + index * 0.02
        row: dict[str, Any] = {
            timestamp_name: timestamp.isoformat(timespec="milliseconds"),
            target_name: round(value, 4),
        }
        if item_id_name:
            row[item_id_name] = "series_A"
        data.append(row)

    return {"data": data}


def send_request(
    *,
    endpoint: str,
    payload: dict[str, Any],
    timeout_ms: int,
    repeat: int,
) -> int:
    try:
        import zmq
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "missing dependency: pyzmq. Install it with `pip install pyzmq`, "
            "or run this script in the project environment that has pyzmq."
        ) from exc

    if timeout_ms <= 0:
        raise SystemExit("--timeout-ms must be greater than 0")
    if repeat <= 0:
        raise SystemExit("--repeat must be greater than 0")

    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.SNDTIMEO, timeout_ms)
    socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
    socket.setsockopt(zmq.LINGER, 0)
    socket.connect(endpoint)

    try:
        request_text = json.dumps(payload, ensure_ascii=False)
        for request_index in range(1, repeat + 1):
            print(f"request #{request_index} -> {endpoint}")
            print(json.dumps(payload, ensure_ascii=False, indent=2))

            socket.send_string(request_text)
            reply_text = socket.recv_string()
            print(f"response #{request_index}:")
            print(format_reply(reply_text))
    except zmq.Again:
        print(
            f"timeout after {timeout_ms} ms. Check endpoint and whether the node is running.",
            file=sys.stderr,
        )
        return 1
    finally:
        socket.close()
        context.term()

    return 0


def format_reply(reply_text: str) -> str:
    try:
        return json.dumps(json.loads(reply_text), ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return reply_text


def main() -> int:
    args = parse_args()
    payload = (
        load_payload(args.input)
        if args.input
        else make_sample_payload(
            target_name=args.target_name,
            timestamp_name=args.timestamp_name,
            item_id_name=args.item_id_name,
            rows=args.rows,
            freq_ms=args.freq_ms,
        )
    )
    return send_request(
        endpoint=args.endpoint,
        payload=payload,
        timeout_ms=args.timeout_ms,
        repeat=args.repeat,
    )


if __name__ == "__main__":
    raise SystemExit(main())
