"""Tests for tool confirmation checks."""

import pytest

from divyaraj.core.safety import ConfirmationRequiredError, ensure_confirmation
from divyaraj.core.tools.get_time import GetTimeTool


class RiskyTestTool(GetTimeTool):
    """Test-only risky tool."""

    name = "risky_test_tool"
    risky = True


def test_safe_tool_does_not_require_confirmation() -> None:
    """Safe tools do not invoke a confirmation callback."""
    ensure_confirmation(GetTimeTool(), lambda tool: pytest.fail("unexpected prompt"))


def test_risky_tool_requires_and_obeys_confirmation() -> None:
    """Risky tools are blocked when confirmation is missing or denied."""
    with pytest.raises(ConfirmationRequiredError, match="explicit confirmation"):
        ensure_confirmation(RiskyTestTool())
    with pytest.raises(ConfirmationRequiredError, match="explicit confirmation"):
        ensure_confirmation(RiskyTestTool(), lambda tool: False)


def test_confirmed_risky_tool_passes() -> None:
    """Explicit user approval allows a risky tool."""
    ensure_confirmation(RiskyTestTool(), lambda tool: True)
