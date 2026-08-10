from app.harness.capabilities import CapabilitySpec
from app.harness.project_gate import run_project_gate


class FakeRunner:
    def __init__(self, exit_code: int = 0) -> None:
        self.exit_code = exit_code

    def module_available(self, name: str) -> bool:
        return False

    def run(self, command: list[str]) -> int:
        return self.exit_code


def capability(identifier: str, *, status: str = "implemented", dependencies: list[str] | None = None) -> CapabilitySpec:
    return CapabilitySpec(
        id=identifier,
        status=status,
        risk_level="write",
        release_suite=status == "implemented",
        command=["echo", identifier] if status == "implemented" else [],
        required_dependencies=dependencies or [],
    )


def test_future_capability_is_reported_without_blocking() -> None:
    report = run_project_gate([capability("refiner", status="future")], runner=FakeRunner())

    assert report.passed is True
    assert report.capability_gaps == ["refiner"]
    assert report.checks[0].status == "capability_gap"


def test_missing_dependency_is_actionable_blocking_failure() -> None:
    report = run_project_gate([capability("mcp_write_path", dependencies=["mcp"])], runner=FakeRunner())

    assert report.passed is False
    assert report.blocking_reasons == ["mcp_write_path:missing_dependency:mcp"]
    assert report.checks[0].reason == "missing_dependency:mcp; install: pip install -e '.[dev]'"


def test_failed_capability_command_is_a_blocking_failure() -> None:
    report = run_project_gate([capability("constitution")], runner=FakeRunner(exit_code=1))

    assert report.checks[0].status == "blocking_failure"
    assert report.blocking_reasons == ["constitution:command_failed"]
