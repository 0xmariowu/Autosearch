from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.scoring import grade, wilson_lower


def test_wilson_lower_zero_total() -> None:
    assert wilson_lower(0, 0) == 0.0


def test_wilson_lower_all_pass() -> None:
    assert wilson_lower(60, 60) == pytest.approx(0.94, rel=1e-2)


def test_wilson_lower_all_fail() -> None:
    assert wilson_lower(0, 60) == 0.0


def test_wilson_lower_single_pass() -> None:
    assert wilson_lower(1, 1) == pytest.approx(0.2065, rel=1e-3)


def test_wilson_lower_sixty_of_sixty() -> None:
    assert wilson_lower(60, 60) == pytest.approx(0.9398, rel=1e-3)


def test_wilson_lower_fifty_of_one_twenty() -> None:
    assert wilson_lower(50, 120) == pytest.approx(0.3322, rel=1e-3)


def test_grade_green() -> None:
    assert grade(0.8, 250, 1200, 60) == "GREEN"


def test_grade_insufficient() -> None:
    assert grade(1.0, 500, 100, 59) == "INSUFFICIENT"


def test_grade_yellow() -> None:
    assert grade(0.5, 100, 7000, 120) == "YELLOW"


def test_grade_red() -> None:
    assert grade(0.2, 300, 800, 120) == "RED"
