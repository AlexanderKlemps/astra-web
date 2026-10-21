import json

import pytest
from pydantic import ValidationError

from astra_web.simulation.schemas.modules import Cavity, Solenoid
from astra_web.simulation.schemas.tables import FieldTable, TravelingWaveHeader


HEADER = {"z1": 0.050021029, "z2": 0.15006119, "n": 1, "m": 3}
SAMPLES = {"z": [0.0, 0.05, 0.1, 0.15, 0.2], "v": [0.0, 1.0, -1.0, 1.0, 0.0]}


@pytest.mark.parametrize("header", [None, HEADER, {**HEADER, "n": -1}])
def test_file_json_file_round_trip(tmp_path, header):
    payload = {**SAMPLES}
    if header is not None:
        payload["traveling_wave"] = header
    original = FieldTable.model_validate(payload)
    source = tmp_path / "field.dat"
    original.to_csv(source)
    decoded = FieldTable.from_csv(source)
    request_json = decoded.model_dump_json(exclude_none=True)
    assert json.loads(request_json) == payload
    restored = FieldTable.model_validate_json(request_json)
    destination = tmp_path / "restored.dat"
    restored.to_csv(destination)
    assert FieldTable.from_csv(destination) == original
    assert source.read_text() == destination.read_text()
    rows = source.read_text().splitlines()
    assert len(rows) == len(SAMPLES["z"]) + (header is not None)
    assert len(rows[0].split()) == (4 if header else 2)
    assert all(len(row.split()) == 2 for row in rows[1:])


def test_header_detection_comments_and_fortran_numbers(tmp_path):
    path = tmp_path / "map.dat"
    path.write_text(
        "\ufeff# metadata follows\n\n"
        "5.0021029D-02 1.5006119E-01 1.0 3.0 ! 120 degree mode\n"
        "\n0D0 0D0\n5D-2 1.0 # a sample\n.1 -1\n.15 1\n.2 0\n",
        encoding="utf-8",
    )
    table = FieldTable.from_csv(path)
    assert table.model_dump() == {**SAMPLES, "traveling_wave": HEADER}
    assert type(table.traveling_wave.n) is int
    assert type(table.traveling_wave.m) is int


@pytest.mark.parametrize("changes", [
    {"z": [0, 1], "v": [0]},
    {"z": [], "v": []},
    {"z": [0], "v": [1]},
    {"z": [0, 0], "v": [0, 1]},
    {"z": [1, 0], "v": [0, 1]},
    {"z": [0, float("inf")], "v": [0, 1]},
    {"z": [0, 1], "v": [0, float("nan")]},
    {"traveling_wave": {**HEADER, "z1": -0.1}},
    {"traveling_wave": {**HEADER, "z2": 0.3}},
])
def test_invalid_samples_and_header_coverage(changes):
    with pytest.raises(ValidationError):
        FieldTable.model_validate({**SAMPLES, **changes})


@pytest.mark.parametrize("changes", [
    {"z1": 1}, {"z2": HEADER["z1"]}, {"z1": float("nan")},
    {"n": 0}, {"n": 1.5}, {"m": 0}, {"m": -3}, {"m": 2.5},
])
def test_invalid_header(changes):
    with pytest.raises(ValidationError):
        TravelingWaveHeader.model_validate({**HEADER, **changes})


@pytest.mark.parametrize("contents", [
    "0 1 2\n1 2\n",  # Wrong column count.
    "0 1\n.1 .2 1 3\n",  # A header is only allowed before the samples.
    ".05 .15 1 3\n.05 .15 1 3\n0 0\n.2 1\n",  # Duplicate header.
    ".05 .15 1 3\n",  # Header without samples.
    ".05 .15 1.5 3\n0 0\n.2 0\n",  # Non-integral phase numerator.
    "0 1\n1 invalid\n",
    "0 1\n1 NaN\n",
])
def test_bad_files_are_rejected(tmp_path, contents):
    path = tmp_path / "bad.dat"
    path.write_text(contents)
    with pytest.raises(ValueError):
        FieldTable.from_csv(path)


@pytest.mark.parametrize("header, filename", [(None, "C2_E.dat"), (HEADER, "TWS_C2_E.dat")])
def test_cavity_namelist_and_written_filename_agree(tmp_path, header, filename):
    table = FieldTable(**SAMPLES, traveling_wave=header)
    cavity = Cavity(id=2, field_table=table, cell_count=6 if header else None)
    cavity.write_to_disk(tmp_path)
    assert cavity.File_Efield == filename
    assert f"File_Efield(2) = '{filename}'" in cavity.to_ini()
    assert ("C_numb(2) = 6" in cavity.to_ini()) == (header is not None)
    assert "traveling_wave" not in cavity.to_ini()
    assert FieldTable.from_csv(tmp_path / filename) == table


def test_solenoids_reject_traveling_wave_metadata():
    with pytest.raises(ValidationError, match="not solenoids"):
        Solenoid(field_table=FieldTable(**SAMPLES, traveling_wave=HEADER))
    assert Solenoid(field_table=FieldTable(**SAMPLES)).File_Bfield == "SNone_B.dat"


@pytest.mark.parametrize("settings", [{}, {"cell_count": None}])
def test_tws_defaults_to_reference_cell_count(settings):
    cavity = Cavity(id=2, field_table={**SAMPLES, "traveling_wave": HEADER}, **settings)
    assert cavity.C_numb == 120
    assert "C_numb(2) = 120" in cavity.to_ini()
    ordinary = Cavity(id=1, field_table=SAMPLES, **settings)
    assert ordinary.C_numb is None
    assert "C_numb" not in ordinary.to_ini()


@pytest.mark.parametrize("settings", [{"cell_count": 6}, {"C_numb": 6}, {"cell_count": 6.0}])
def test_tws_cell_count_can_be_overridden(settings):
    cavity = Cavity(id=2, field_table={**SAMPLES, "traveling_wave": HEADER}, **settings)
    assert cavity.C_numb == 6
    assert "C_numb(2) = 6" in cavity.to_ini()


@pytest.mark.parametrize("count", [1, 119, 121])
def test_incompatible_tws_cell_count_is_rejected(count):
    with pytest.raises(ValidationError, match="must be an integer"):
        Cavity(field_table={**SAMPLES, "traveling_wave": HEADER}, cell_count=count)


@pytest.mark.parametrize("n", [2, -2])
def test_cell_count_checks_the_phase_ratio_not_only_the_denominator(n):
    header = {**HEADER, "n": n, "m": 6}
    cavity = Cavity(field_table={**SAMPLES, "traveling_wave": header}, cell_count=3)
    assert cavity.C_numb == 3


def test_incompatible_default_requires_an_explicit_cell_count():
    with pytest.raises(ValidationError, match="must be an integer"):
        Cavity(field_table={**SAMPLES, "traveling_wave": {**HEADER, "m": 7}})
