"""Punkt wejścia: tap32 [--simulate] [--minimized] [--config PLIK] [--verbose]."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tap32", description="Tap32 – konfiguracja macropada")
    parser.add_argument(
        "--simulate", action="store_true", help="użyj symulatora zamiast urządzenia"
    )
    parser.add_argument(
        "--board",
        choices=["kb2040", "xiao_esp32s3"],
        default="kb2040",
        help="płytka zgłaszana przez symulator",
    )
    parser.add_argument("--minimized", action="store_true", help="start w zasobniku")
    parser.add_argument("--config", type=Path, help="ścieżka pliku konfiguracji")
    parser.add_argument("--verbose", action="store_true", help="szczegółowy dziennik na konsoli")
    parser.add_argument("--version", action="version", version=f"Tap32 {__version__}")
    args = parser.parse_args(argv)

    from .gui.app import run

    return run(
        simulate=args.simulate,
        minimized=args.minimized,
        config_path=args.config,
        verbose=args.verbose,
        board=args.board,
    )


if __name__ == "__main__":
    sys.exit(main())
