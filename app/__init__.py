"""
App package initializer with compatibility shims.

Includes a monkey patch for Python 3.9 where importlib.metadata lacks
`packages_distributions`, which some third-party libraries expect.
"""
from __future__ import annotations

import sys

# --- Compat: ensure importlib.metadata has packages_distributions on Python 3.9 ---
try:
    import importlib.metadata as _im  # type: ignore
except Exception:  # pragma: no cover - extremely unlikely
    _im = None  # type: ignore

if _im and not hasattr(_im, "packages_distributions"):
    try:
        import importlib_metadata as _im_backport  # type: ignore

        _im.packages_distributions = _im_backport.packages_distributions  # type: ignore
        sys.modules["importlib.metadata"] = _im
    except Exception:
        # Fallback stub to avoid AttributeError even if backport unavailable
        def _stub_packages_distributions():  # type: ignore
            return {}

        _im.packages_distributions = _stub_packages_distributions  # type: ignore
        sys.modules["importlib.metadata"] = _im

__all__ = []
