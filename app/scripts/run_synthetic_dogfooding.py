"""CLI for the isolated synthetic dogfooding replay."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.harness.synthetic.runner import run_synthetic_dogfooding


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay Cockpit synthetic dogfooding fixtures")
    parser.add_argument(
        "--output",
        type=Path,
        help="Directory for replay artefacts (default: a new temporary directory)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output or Path(tempfile.mkdtemp(prefix="cockpit-synthetic-dogfood-"))
    replay = run_synthetic_dogfooding(output_dir=output_dir)
    print(f"Synthetic replay completed for {len(replay.personas)} personas: {output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
