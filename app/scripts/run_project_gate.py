"""CLI for Cockpit's local project release gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.harness.capabilities import load_capabilities  # noqa: E402
from app.harness.project_gate import run_project_gate  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Cockpit's project quality gate")
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_project_gate(load_capabilities(args.registry))
    encoded = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2)
    if args.output:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
