import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from astra_web.simulation.schemas import io as simulation_io
from astra_web.simulation.schemas.modules import Aperture
from astra_web.simulation.schemas.tables import ApertureTable


CONTOUR = {"z": [0.0, 0.1, 0.1, 0.2], "radius": [5.0, 5.0, 2.0, 2.0]}


def test_contour_round_trip_preserves_steps_and_radius_units(tmp_path):
    source = tmp_path / "contour.dat"
    source.write_text("\ufeff! z [m], radius [mm]\n0D0 5D0\n.1 5\n.1 2 # step\n\n.2 2\n")
    table = ApertureTable.from_csv(source)
    assert table.model_dump() == CONTOUR
    restored = ApertureTable.model_validate_json(table.model_dump_json())
    destination = tmp_path / "restored.dat"
    restored.to_csv(destination)
    assert ApertureTable.from_csv(destination) == table
    assert destination.read_text().splitlines() == ["0.0 5.0", "0.1 5.0", "0.1 2.0", "0.2 2.0"]


@pytest.mark.parametrize("changes", [
    {"z": [0], "radius": [1]},
    {"radius": [1, 2]},
    {"z": [0, 0.2, 0.1, 0.3]},
    {"z": [0, 0, 0, 0]},
    {"radius": [1, -1, 1, 1]},
    {"radius": [1, float("inf"), 1, 1]},
    {"z": [0, 0.1, float("nan"), 0.2]},
    {"traveling_wave": {"z1": 0, "z2": 0.2, "n": 1, "m": 3}},
])
def test_invalid_contours_are_rejected(changes):
    with pytest.raises(ValidationError):
        ApertureTable.model_validate({**CONTOUR, **changes})


@pytest.mark.parametrize("contents", ["", "0 1 1 3\n0 5\n1 5\n", "0 5\n1 invalid\n", "0 5\n1 NaN\n"])
def test_invalid_contour_files_are_rejected(tmp_path, contents):
    path = tmp_path / "bad.dat"
    path.write_text(contents)
    with pytest.raises(ValueError):
        ApertureTable.from_csv(path)


@pytest.mark.parametrize("keyword, radius", [
    ("RAD", 2.0), ("rad", -2.0), ("Scr_X", -1.0), ("Scr_Y", 1.0),
    ("Col_X", 2.0), ("Col_Y", 3.0),
])
def test_keyword_geometry_export_preserves_signed_radius(tmp_path, keyword, radius):
    aperture = Aperture(id=3, type=keyword, z_start=0.1, z_end=0.11, radius=radius,
                        z_offset=0.5, x_offset=0.001, xz_rotation=0.002)
    ini = aperture.to_ini()
    assert f"File_Aperture(3) = '{'RAD' if keyword == 'rad' else keyword}'" in ini
    assert f"Ap_R(3) = {radius}" in ini
    assert "Ap_Z1(3) = 0.1" in ini
    assert "Ap_Z2(3) = 0.11" in ini
    assert "A_pos(3) = 0.5" in ini
    assert "A_xoff(3) = 0.001" in ini
    assert "A_xrot(3) = 0.002" in ini
    assert aperture.z_0 == pytest.approx(0.6)
    aperture.write_to_disk(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_circular_grid_export_preserves_both_indices():
    aperture = Aperture(id=2, type="CIR", z_start=0, z_end=0.001, grid_radii=[0, 1, 2, 3])
    ini = aperture.to_ini()
    assert "File_Aperture(2) = 'Cir'" in ini
    assert "Ap_GR(2,1) = 0.0" in ini
    assert "Ap_GR(2,4) = 3.0" in ini
    assert "Ap_R(" not in ini
    assert aperture.model_dump()["Ap_GR(2,3)"] == 2.0


@pytest.mark.parametrize("payload", [
    {},
    {"type": "unsupported"},
    {"aperture_table": CONTOUR, "radius": 1},
    {"aperture_table": CONTOUR, "z_start": 0, "z_end": 1},
    {"type": "RAD", "z_start": 0, "z_end": 1, "radius": 1, "aperture_table": CONTOUR},
    {"type": "RAD", "z_start": 1, "z_end": 1, "radius": 1},
    {"type": "RAD", "z_end": 1, "radius": 1},
    {"type": "RAD", "z_start": 0, "z_end": 1},
    {"type": "RAD", "z_start": 0, "z_end": 1, "radius": 1, "grid_radii": [0, 1]},
    {"type": "Col_X", "z_start": 0, "z_end": 1, "radius": -1},
    {"type": "Col_Y", "z_start": 0, "z_end": 1, "radius": 0},
    {"type": "RAD", "z_start": 0, "z_end": 1, "radius": float("nan")},
    {"aperture_table": CONTOUR, "z_offset": float("inf")},
    {"aperture_table": CONTOUR, "SE_d0": 1},
])
def test_missing_conflicting_or_invalid_geometry_is_rejected(payload):
    with pytest.raises(ValidationError):
        Aperture.model_validate(payload)


@pytest.mark.parametrize("radii", [None, [], [0, 1, 2], [-1, 1], [1, 1], [2, 1], [0, 2, 1, 3], list(range(42))])
def test_invalid_grid_rings_are_rejected(radii):
    with pytest.raises(ValidationError):
        Aperture(type="Cir", z_start=0, z_end=1, grid_radii=radii)


def test_aperture_only_request_sorts_by_shifted_start_and_writes_table(tmp_path, monkeypatch):
    monkeypatch.setattr(simulation_io, "SIMULATION_DATA_PATH", str(tmp_path))
    request = simulation_io.SimulationInput.model_validate_json(json.dumps({
        "apertures": [
            {"aperture_table": CONTOUR, "z_offset": 1},
            {"type": "RAD", "z_start": 0.4, "z_end": 0.5, "radius": 3},
        ],
    }))
    assert [a.id for a in request.apertures] == [1, 2]
    assert [a.File_Aperture for a in request.apertures] == ["RAD", "A2.dat"]
    ini = request.write_to_disk()
    assert "&APERTURE\n    LApert = true\n" in ini
    assert "File_Aperture(1) = 'RAD'" in ini
    assert "File_Aperture(2) = 'A2.dat'" in ini
    assert ApertureTable.from_csv(Path(request.run_dir) / "A2.dat").model_dump() == CONTOUR
    summary = json.loads((Path(request.run_dir) / "input.json").read_text())
    assert summary["gun_phase"] is None
    assert summary["solenoid_strength"] is None


def test_empty_apertures_remain_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(simulation_io, "SIMULATION_DATA_PATH", str(tmp_path))
    request = simulation_io.SimulationInput()
    ini = request.write_to_disk()
    assert "&APERTURE\n    LApert = false\n/" in ini
    assert list(Path(request.run_dir).glob("A*.dat")) == []
