"""PyInstaller build wrapper for the TrainGluonTS CLI."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    """Build the packaging command parser."""
    parser = argparse.ArgumentParser(prog="python -m traingluonts.packaging.build")
    parser.add_argument(
        "--target",
        choices=["cli", "workflow-node"],
        default="cli",
        help="entrypoint target to package",
    )
    parser.add_argument(
        "--mode",
        choices=["onedir", "onefile"],
        default="onedir",
        help="PyInstaller output mode",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="binary executable name",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="clean PyInstaller cache before building",
    )
    parser.add_argument(
        "--output-dir",
        default="dist",
        help="directory for build artifacts",
    )
    parser.add_argument(
        "--build-dir",
        default="build/pyinstaller",
        help="directory for PyInstaller work files",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Build a PyInstaller binary distribution."""
    args = build_parser().parse_args(argv)

    if importlib.util.find_spec("PyInstaller") is None:
        print(
            "PyInstaller is not installed. Install packaging dependencies with "
            "`pip install .[packaging]` or `uv pip install -e .[packaging]`.",
            file=sys.stderr,
        )
        return 2

    repo_root = Path(__file__).resolve().parents[3]
    source_root = repo_root / "src"
    entrypoint = _entrypoint_for_target(args.target, source_root)
    name = args.name or _default_name_for_target(args.target)
    output_dir = _root_relative(args.output_dir, repo_root)
    build_dir = _root_relative(args.build_dir, repo_root)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--name",
        name,
        "--distpath",
        str(output_dir),
        "--workpath",
        str(build_dir),
        "--specpath",
        str(build_dir),
        "--paths",
        str(source_root),
        "--collect-data",
        "gluonts",
    ]

    if args.clean:
        command.append("--clean")

    command.append("--onefile" if args.mode == "onefile" else "--onedir")
    command.extend(_collect_submodule_options())
    command.append(str(entrypoint))

    print("Running PyInstaller:")
    print(" ".join(command))
    completed = subprocess.run(command, check=False)
    return completed.returncode


def _collect_submodule_options() -> list[str]:
    options: list[str] = []
    for package in ("gluonts", "lightning", "pytorch_lightning", "torchmetrics"):
        if importlib.util.find_spec(package) is not None:
            options.extend(["--collect-submodules", package])
    return options


def _entrypoint_for_target(target: str, source_root: Path) -> Path:
    if target == "cli":
        return source_root / "traingluonts" / "cli" / "main.py"
    if target == "workflow-node":
        return source_root / "traingluonts" / "workflow_node" / "main.py"
    raise ValueError(f"unsupported package target: {target}")


def _default_name_for_target(target: str) -> str:
    if target == "cli":
        return "traingluonts"
    if target == "workflow-node":
        return "traingluonts-workflow-node"
    raise ValueError(f"unsupported package target: {target}")


def _root_relative(path: str, repo_root: Path) -> Path:
    value = Path(path).expanduser()
    if value.is_absolute():
        return value
    return repo_root / value


if __name__ == "__main__":
    raise SystemExit(main())
