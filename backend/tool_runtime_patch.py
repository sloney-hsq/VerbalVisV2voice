"""Retired compatibility module.

The unified ``tools.py`` owns product-revenue semantics and comparison refresh,
so runtime monkey patches are no longer required. This file remains import-safe
for older scripts.
"""


def install_product_revenue_alias() -> None:
    return None


def install_tool_refresh_patch() -> None:
    return None
