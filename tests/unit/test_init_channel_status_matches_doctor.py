"""Bug 2 (fix-plan): `autosearch doctor` and `autosearch init --check-channels`
used to disagree on channel availability counts (e.g. 37/40 vs 38/40) because
they ran two independent availability pipelines. This pins them to the same
doctor source of truth so the divergence cannot return."""

from __future__ import annotations

from autosearch.core.doctor import scan_channels
from autosearch.init.channel_status import (
    compile_channel_statuses,
    default_channels_root,
)


def test_init_check_channels_total_matches_doctor() -> None:
    doctor_rows = scan_channels()
    init_rows = compile_channel_statuses(default_channels_root())
    assert len(init_rows) == len(doctor_rows), (
        f"channel total diverged: doctor={len(doctor_rows)} init={len(init_rows)}"
    )


def test_init_check_channels_available_count_matches_doctor_ok_count() -> None:
    doctor_rows = scan_channels()
    init_rows = compile_channel_statuses(default_channels_root())
    doctor_ok = sum(1 for r in doctor_rows if r.status == "ok")
    init_avail = sum(1 for r in init_rows if r.status == "available")
    assert init_avail == doctor_ok, (
        f"available count diverged: doctor={doctor_ok} init={init_avail}; "
        "init must use doctor as the single source of truth (plan §F003)"
    )


def test_init_per_channel_availability_matches_doctor() -> None:
    doctor_rows = {r.channel: r for r in scan_channels()}
    init_rows = compile_channel_statuses(default_channels_root())
    mismatches: list[str] = []
    for ir in init_rows:
        dr = doctor_rows.get(ir.channel)
        assert dr is not None, f"init row {ir.channel} has no doctor counterpart"
        init_says_available = ir.status == "available"
        doctor_says_ok = dr.status == "ok"
        if init_says_available != doctor_says_ok:
            mismatches.append(f"{ir.channel}: doctor={dr.status} init={ir.status}")
    assert not mismatches, "per-channel availability disagreement:\n" + "\n".join(mismatches)
