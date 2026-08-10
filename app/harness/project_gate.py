"""Local release gate that combines Cockpit capability contracts."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel

from app.harness.capabilities import CapabilitySpec, PROJECT_ROOT


class CommandRunner(Protocol):
    def module_available(self, name: str) -> bool: ...

    def run(self, command: list[str]) -> int: ...


class SubprocessRunner:
    def module_available(self, name: str) -> bool:
        return importlib.util.find_spec(name) is not None

    def run(self, command: list[str]) -> int:
        return subprocess.run(command, cwd=PROJECT_ROOT, check=False).returncode


class CheckResult(BaseModel):
    id: str
    status: Literal["passed", "blocking_failure", "capability_gap"]
    reason: str | None = None
    command: list[str]


class ProjectGateReport(BaseModel):
    passed: bool
    checks: list[CheckResult]
    capability_gaps: list[str]
    blocking_reasons: list[str]


def run_project_gate(
    capabilities: list[CapabilitySpec], runner: CommandRunner | None = None
) -> ProjectGateReport:
    """Run release-scoped capabilities and report future entries separately."""

    active_runner = runner or SubprocessRunner()
    checks: list[CheckResult] = []
    gaps: list[str] = []
    blockers: list[str] = []
    for capability in capabilities:
        if capability.status == "future":
            gaps.append(capability.id)
            checks.append(CheckResult(id=capability.id, status="capability_gap", command=[]))
            continue
        missing = next(
            (name for name in capability.required_dependencies if not active_runner.module_available(name)),
            None,
        )
        if missing:
            blockers.append(f"{capability.id}:missing_dependency:{missing}")
            checks.append(
                CheckResult(
                    id=capability.id,
                    status="blocking_failure",
                    reason=f"missing_dependency:{missing}; install: pip install -e '.[dev]'",
                    command=capability.command,
                )
            )
            continue
        if not capability.release_suite:
            checks.append(CheckResult(id=capability.id, status="passed", command=[]))
            continue
        if active_runner.run(capability.command) != 0:
            blockers.append(f"{capability.id}:command_failed")
            checks.append(
                CheckResult(
                    id=capability.id,
                    status="blocking_failure",
                    reason="command_failed",
                    command=capability.command,
                )
            )
            continue
        checks.append(CheckResult(id=capability.id, status="passed", command=capability.command))
    return ProjectGateReport(
        passed=not blockers,
        checks=checks,
        capability_gaps=gaps,
        blocking_reasons=blockers,
    )
