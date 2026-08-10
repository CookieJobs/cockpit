"""Run the Achievement Distillation Harness dataset from the command line."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import cast

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.harness.adapter import DistillationAdapter, FakeAdapter, PolishCvAdapter  # noqa: E402
from app.harness.datasets import load_cases  # noqa: E402
from app.harness.gate import evaluate_gate  # noqa: E402
from app.harness.models import (  # noqa: E402
    AchievementDistillationCase,
    AchievementDistillationOutput,
    HarnessReport,
)
from app.harness.report import summarize  # noqa: E402
from app.harness.runner import run_cases  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Achievement Distillation Harness cases")
    parser.add_argument("--dataset", help="Path to a dataset JSON file")
    parser.add_argument("--output", help="Write report JSON to this path instead of stdout")
    parser.add_argument("--category", choices=("golden", "boundary", "adversarial"))
    parser.add_argument(
        "--fake-fixture",
        action="store_true",
        help="Use deterministic fixture outputs and never call an LLM",
    )
    parser.add_argument("--gate", action="store_true", help="Apply v1 release thresholds and use its exit code")
    return parser.parse_args()


def fake_output(case: AchievementDistillationCase) -> AchievementDistillationOutput:
    """Produce a deterministic, parseable output for runner and report verification."""
    return AchievementDistillationOutput(
        cv=f"优化{case.input.task_title}：{case.input.outcome}"[:80],
        follow_up_questions=[],
        generator_status="polished",
    )


async def main_async(args: argparse.Namespace) -> dict[str, object]:
    cases = load_cases(args.dataset)
    if args.category:
        cases = [case for case in cases if case.category == args.category]

    if args.fake_fixture:
        adapter: DistillationAdapter = FakeAdapter({case.id: fake_output(case) for case in cases})
    else:
        adapter = PolishCvAdapter()

    report = summarize(await run_cases(cases, adapter))
    return cast(dict[str, object], report.model_dump(mode="json"))


def main() -> int:
    args = parse_args()
    report_payload = asyncio.run(main_async(args))
    exit_code = 0
    if args.gate:
        report = HarnessReport.model_validate(report_payload)
        decision = evaluate_gate(report)
        report_payload["gate"] = decision.model_dump(mode="json")
        exit_code = 0 if decision.passed else 1
    encoded = json.dumps(report_payload, ensure_ascii=False, sort_keys=True, indent=2)
    if args.output:
        Path(args.output).write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
