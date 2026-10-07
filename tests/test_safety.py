"""Tests for tool confirmation checks."""

import pytest

from divyaraj.core.safety import ConfirmationRequiredError, ensure_confirmation
from divyaraj.core.tools.get_time import GetTimeTool


class RiskyTestTool(GetTimeTool):
    """Test-only risky tool."""

    name = "risky_test_tool"
    risky = True


def test_safe_tool_does_not_require_confirmation() -> None:
    """Safe tools can pass the safety check without confirmation."""
    ensure_confirmation(GetTimeTool())


def test_risky_tool_requires_explicit_confirmation() -> None:
    """Risky tools are blocked until confirmation is provided."""
    with pytest.raises(
        ConfirmationRequiredError, match="requires explicit confirmation"
    ):
        ensure_confirmation(RiskyTestTool())


def test_confirmed_risky_tool_passes() -> None:
    """Explicit confirmation allows a risky tool to pass the check."""
    ensure_confirmation(RiskyTestTool(), confirmed=True)
