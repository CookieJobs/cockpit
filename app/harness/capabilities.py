"""Versioned capability registry for the local project quality gate."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "docs" / "harness" / "capabilities-v1.yaml"


class CapabilitySpec(BaseModel):
    """One Cockpit capability and its release-gate contract."""

    model_config = ConfigDict(extra="forbid")

    id: str
    status: Literal["implemented", "future"]
    risk_level: Literal["read", "write", "destructive"]
    release_suite: bool
    command: list[str]
    required_dependencies: list[str]

    @model_validator(mode="after")
    def validate_release_contract(self) -> "CapabilitySpec":
        if self.status == "future" and self.release_suite:
            raise ValueError("future capability cannot set release_suite")
        if self.status == "implemented" and not self.command:
            raise ValueError("implemented capability requires a command")
        return self


class CapabilityRegistry(BaseModel):
    """Strict top-level shape for a capability registry file."""

    model_config = ConfigDict(extra="forbid")

    capabilities: list[CapabilitySpec]


def load_capabilities(path: Path | None = None) -> list[CapabilitySpec]:
    """Load the registry and reject malformed or duplicate capability ids."""

    registry_path = path or DEFAULT_REGISTRY_PATH
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    registry = CapabilityRegistry.model_validate(payload)
    ids = [capability.id for capability in registry.capabilities]
    if len(ids) != len(set(ids)):
        raise ValueError("capability ids must be unique")
    return registry.capabilities
