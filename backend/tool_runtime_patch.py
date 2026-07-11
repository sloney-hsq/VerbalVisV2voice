"""Small runtime patch for dashboard refresh ownership.

Managed comparison views are queried by ``demo_tools`` because they use fixed
study semantics (product revenue and order-category delivery grain). The legacy
generic refresh function must not try to rebuild those views with its generic
aggregation expressions.

This module only separates refresh ownership. It does not add cancellation,
rollback, epochs, transactions, or stale-result handling.
"""

from __future__ import annotations

from typing import Callable

import tools


_ORIGINAL_REFRESH: Callable[[], None] | None = None


def install_tool_refresh_patch() -> None:
    """Make the legacy refresh function skip managed comparison views."""
    global _ORIGINAL_REFRESH
    if getattr(tools, "_verbalvis_managed_refresh_patch", False):
        return

    original_refresh = tools._refresh_all_views
    _ORIGINAL_REFRESH = original_refresh

    def refresh_non_managed_views() -> None:
        managed = [view for view in tools.views if view.get("managed_comparison")]
        if not managed:
            original_refresh()
            return

        all_views = tools.views
        tools.views = [view for view in all_views if not view.get("managed_comparison")]
        try:
            original_refresh()
        finally:
            tools.views = all_views

    tools._refresh_all_views = refresh_non_managed_views
    tools._verbalvis_managed_refresh_patch = True


install_tool_refresh_patch()
