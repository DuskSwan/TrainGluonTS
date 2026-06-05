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
        "--mode",
        choices=["onedir", "onefile"],
        default="onedir",
        help="PyInstaller output mode",
    )
    parser.add_argument(
        "--name",
        default="traingluonts",
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
    entrypoint = source_root / "traingluonts" / "cli" / "main.py"
    output_dir = _root_relative(args.output_dir, repo_root)
    build_dir = _root_relative(args.build_dir, repo_root)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--name",
        args.name,
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


def _root_relative(path: str, repo_root: Path) -> Path:
    value = Path(path).expanduser()
    if value.is_absolute():
        return value
    return repo_root / value


if __name__ == "__main__":
    raise SystemExit(main())

