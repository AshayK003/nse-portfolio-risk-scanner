"""Smoke test: every UI module must import cleanly at module load.

This catches package-namespace drift between ``ui/`` and ``engine/`` before
it reaches Streamlit Cloud (e.g. a name used in ``ui`` but never re-exported
by ``engine/__init__.py``). Pure import check — no rendering, no network.
"""

from __future__ import annotations

import importlib
import pkgutil

import pytest

import ui


def _discover_ui_modules():
    """Return dotted names of all importable submodules under ``ui``."""
    names = []
    for mod in pkgutil.iter_modules(ui.__path__, prefix=f"{ui.__name__}."):
        names.append(mod.name)
    return sorted(names)


_UI_MODULES = _discover_ui_modules()


@pytest.mark.parametrize("module_name", _UI_MODULES)
def test_ui_module_imports(module_name: str) -> None:
    # A failed import here surfaces the real ModuleNotFoundError/ImportError
    # with the missing name — exactly the startup crash class this guards.
    importlib.import_module(module_name)
