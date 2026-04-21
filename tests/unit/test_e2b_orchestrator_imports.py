"""Guard that the ported e2b orchestrator modules still import cleanly from
their repo-relative location. Runs without e2b_code_interpreter installed —
we only touch the pure-python helper modules (matrix / packing / secrets),
skipping the ones that require the external SDK.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "scripts" / "e2b" / "lib"


def _load(name: str):
    path = LIB_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_lib_matrix_imports():
    m = _load("matrix")
    assert hasattr(m, "load_matrix")
    assert hasattr(m, "PhaseSpec")


def test_lib_packing_imports():
    m = _load("packing")
    assert hasattr(m, "pack_directory")


def test_lib_secrets_imports():
    m = _load("secrets")
    assert hasattr(m, "load_secrets")
