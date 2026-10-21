import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError

from astra_web.simulation.schemas import io as simulation_io


SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "parse_astra_input.py"
spec = importlib.util.spec_from_file_location("parse_astra_input", SCRIPT)
converter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(converter)


@pytest.fixture
def astra_input(tmp_path):
    (tmp_path / "cavity,!map.dat").write_text("! z E\n0D0 1D0\n0.5 2.5 # peak\n")
    (tmp_path / "solenoid.dat").write_text("0 -1.5\n1 0\n")
    path = tmp_path / "run.in"
    path.write_text("""
&NEWRUN
    Head = 'Beam''s run / with ! and , inside a string'
    Distribution = '/app/data/generator/beam.ini'
    Version = 4, RUN = 2, XYrms = 2.16D-1, Trms = 9D-3
    H_min = 0, H_max = .001, Track_All = .T., Auto_Phase = false
/
&OUTPUT ZSTART = 0, ZSTOP = 3.2, High_res = .true., RefS = TRUE /
&CHARGE LSPCH = true, z_trans = 1, L2D_3D = .true., Nxf = 32 /
&CAVITY
    LEfield = true
    File_Efield(10) = 'cavity,!map.dat', C_pos(10) = 1, Phi(10) = 7
    File_Efield(2) = 'cavity,!map.dat', C_pos(2) = 0, Phi(2) = -4.46d0
    MaxE(2) = 58.1, Nue(2) = 1.3, C_smooth(2) = 0, C_higher_order(2) = F
/
&SOLENOID LBfield = .true., MaxB(1) = -.216, File_Bfield(1) = 'solenoid.dat' /
&QUADRUPOLE LQUAD = true, Q_length(3) = .1, Q_K(3) = -2, Q_Bore(3) = .035, Q_pos(3) = 2 /
""")
    return path


def test_namelist_syntax_and_quoted_delimiters(astra_input):
    sections = converter.parse_namelists(astra_input.read_text())
    run = sections["newrun"]
    assert run["head", None] == "Beam's run / with ! and , inside a string"
    assert run["xyrms", None] == 0.216
    assert run["track_all", None] is True
    assert run["auto_phase", None] is False
    assert sections["cavity"]["phi", 2] == -4.46


def test_conversion_uses_api_aliases_and_embeds_maps(astra_input, monkeypatch, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    result = converter.convert_input(astra_input)
    assert result["run_specs"] == {
        "Version": 4, "run_number": 2, "rms_laser_spot_size": 0.216,
        "rms_emission_time": 0.009, "min_time_step": 0, "max_time_step": 0.001,
        "track_all_particles": True, "auto_phase": False, "particle_file_name": "beam",
    }
    assert result["output_specs"] == {
        "z_start": 0, "z_stop": 3.2, "high_accuracy": True, "generate_reference_output": True,
    }
    assert result["space_charge"] == {"use_space_charge": True, "z_trans": 1, "3D_x_grid_size": 32}
    assert [module["phase"] for module in result["cavities"]] == [-4.46, 7]
    cavity = result["cavities"][0]
    assert cavity["field_table"] == {"z": [0.0, 0.5], "v": [1.0, 2.5]}
    assert cavity["higher_order"] is False
    assert cavity["frequency"] == 1.3
    assert cavity["max_field_strength"] == 58.1
    assert result["solenoids"][0]["max_field_strength"] == -0.216
    assert result["quadrupoles"] == [{
        "effective_length": .1, "focusing_strength": -2, "fringe_taper_length": .035, "z_center": 2,
    }]
    assert not (tmp_path / "input.json").exists()
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setattr(simulation_io, "SIMULATION_DATA_PATH", str(runs))
    request = simulation_io.SimulationInput.model_validate_json(json.dumps(result))
    assert request.run_specs.XYrms == .216
    assert request.cavities[0].field_table.v == [1, 2.5]
    assert request.quadrupoles[0].Q_K == -2


def test_api_namelist_round_trip(astra_input, monkeypatch, tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setattr(simulation_io, "SIMULATION_DATA_PATH", str(runs))
    request = simulation_io.SimulationInput.model_validate(converter.convert_input(astra_input))
    request.write_to_disk()
    restored = simulation_io.SimulationInput.model_validate(converter.convert_input(Path(request.input_filename)))
    assert restored.to_ini() == request.to_ini()
    assert restored.cavities[0].field_table == request.cavities[0].field_table
    assert restored.solenoids[0].field_table == request.solenoids[0].field_table


def test_disabled_modules_do_not_read_unused_maps(astra_input):
    astra_input.write_text("""
&NEWRUN Distribution = 'beam.ini' /
&CAVITY LEfield = false, File_Efield(1) = 'missing.dat' /
&SOLENOID LBfield = false /
&QUADRUPOLE LQUAD = false /
""")
    result = converter.convert_input(astra_input)
    assert result["cavities"] == result["solenoids"] == result["quadrupoles"] == []


def test_field_map_relocation_and_particle_override(astra_input):
    astra_input.write_text(astra_input.read_text().replace("'solenoid.dat'", "'/container/solenoid.dat'"))
    result = converter.convert_input(astra_input, field_map_dir=astra_input.parent, particle_id="registered-beam")
    assert result["solenoids"][0]["field_table"]["v"] == [-1.5, 0]
    assert result["run_specs"]["particle_file_name"] == "registered-beam"


@pytest.mark.parametrize("text, message", [
    ("&NEWRUN RUN = 1", "Unterminated"),
    ("&NEWRUN RUN = /", "expected a finite number"),
    ("&NEWRUN RUN = 1 RUN = 2 /", "Duplicate assignment"),
    ("&NEWRUN / &NEWRUN /", "Duplicate namelist"),
    ("&CAVITY MaxE(0) = 1 /", "positive integer"),
    ("&CAVITY Phi(1:3) = 1 /", "unsupported syntax"),
    ("&CAVITY Phi = 1,2,3 /", "expected name"),
    ("&NEWRUN H_max = 1e999 /", "expected a finite number"),
    ("&NEWRUN Head = 'unterminated /", "unsupported syntax"),
])
def test_malformed_or_unsupported_syntax(text, message):
    with pytest.raises(converter.ConversionError, match=message):
        converter.parse_namelists(text)


def test_end_terminators_and_double_quoted_strings():
    result = converter.parse_namelists('$newrun Head = "a ""quote""" &end ! comment\n&output ZSTOP=1 $END')
    assert result["newrun"]["head", None] == 'a "quote"'
    assert result["output"]["zstop", None] == 1


@pytest.mark.parametrize("extra, message", [
    ("&DIPOLE LDipole = true /", "Namelists not supported"),
    ("&OUTPUT UnknownSetting = 1 /", "not supported by the REST API"),
    ("&CHARGE L2D_3D = false, z_trans = 1 /", "conflicts with z_trans"),
    ("&CHARGE L2D_3D = true /", "conflicts with z_trans"),
    ("&CAVITY LEfield = true /", "no module settings"),
    ("&CAVITY LEfield = true, Phi(1) = 1 /", "must name a field map"),
    ("&QUADRUPOLE LQUAD = true, Q_K = 2 /", "explicit module index"),
])
def test_unrepresentable_settings_fail_explicitly(tmp_path, extra, message):
    path = tmp_path / "run.in"
    path.write_text("&NEWRUN Distribution='beam.ini' /\n" + extra)
    with pytest.raises(converter.ConversionError, match=message):
        converter.convert_input(path)


def test_schema_constraints_are_validated(astra_input):
    astra_input.write_text(astra_input.read_text().replace("Nxf = 32", "Nxf = 2"))
    with pytest.raises(ValidationError):
        converter.convert_input(astra_input)


@pytest.mark.parametrize("precision, reference", [(False, True), (True, False), (False, False), (True, True)])
def test_output_switches_convert_independently_and_round_trip(astra_input, tmp_path, monkeypatch, precision, reference):
    astra_input.write_text(astra_input.read_text().replace(
        "High_res = .true., RefS = TRUE",
        f"High_res = {str(precision).lower()}, RefS = {str(reference).lower()}",
    ))
    payload = converter.convert_input(astra_input)
    assert payload["output_specs"]["high_accuracy"] is precision
    assert payload["output_specs"]["generate_reference_output"] is reference
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setattr(simulation_io, "SIMULATION_DATA_PATH", str(runs))
    request = simulation_io.SimulationInput.model_validate_json(json.dumps(payload))
    request.write_to_disk()
    restored = converter.convert_input(Path(request.input_filename))
    assert restored["output_specs"]["high_accuracy"] is precision
    assert restored["output_specs"]["generate_reference_output"] is reference
    assert "min_time_step" in restored["run_specs"]
    assert "z_offset" in restored["cavities"][0]
    assert "z_center" in restored["quadrupoles"][0]


def test_precision_setting_can_be_converted_without_reference_setting(tmp_path):
    source = tmp_path / "run.in"
    source.write_text("&NEWRUN Distribution='beam.ini' / &OUTPUT High_res=false /")
    payload = converter.convert_input(source)
    assert payload["output_specs"] == {"high_accuracy": False}
    assert simulation_io.SimulationOutputSpecification(**payload["output_specs"]).RefS is True


@pytest.mark.parametrize("contents", ["", "0 1 2", "0 nan", "0 nope"])
def test_invalid_field_maps_are_rejected(tmp_path, contents):
    path = tmp_path / "field.dat"
    path.write_text(contents)
    with pytest.raises(converter.ConversionError):
        converter.read_field_table(path)


def test_cli_writes_default_output_from_another_directory(astra_input, tmp_path):
    result = subprocess.run([sys.executable, str(SCRIPT), str(astra_input)],
                            cwd=tmp_path.parent, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    output = astra_input.with_name("simulation_in.json")
    assert json.loads(output.read_text())["run_specs"]["particle_file_name"] == "beam"


def test_cli_error_preserves_existing_output(astra_input):
    output = astra_input.with_name("simulation_in.json")
    output.write_text("existing output")
    (astra_input.parent / "solenoid.dat").unlink()
    result = subprocess.run([sys.executable, str(SCRIPT), str(astra_input), "-o", str(output)],
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert "solenoid.dat" in result.stderr
    assert "Traceback" not in result.stderr
    assert output.read_text() == "existing output"


def test_cli_refuses_to_overwrite_source(astra_input):
    original = astra_input.read_text()
    result = subprocess.run([sys.executable, str(SCRIPT), str(astra_input), "-o", str(astra_input)],
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert astra_input.read_text() == original


def test_traveling_wave_survives_simulation_request_and_disk_write(astra_input, monkeypatch, tmp_path):
    from astra_web.simulation.schemas.tables import FieldTable

    source_map = tmp_path / "cavity,!map.dat"
    source_map.write_text(".05 .15 1.0 3.0\n0 0\n.05 1\n.1 -1\n.15 1\n.2 0\n")
    astra_input.write_text(astra_input.read_text().replace(
        "LEfield = true", "LEfield = true, C_numb(2) = 6, C_numb(10) = 6"
    ))
    payload = converter.convert_input(astra_input)
    assert payload["cavities"][0]["cell_count"] == 6
    assert payload["cavities"][0]["field_table"]["traveling_wave"] == {
        "z1": .05, "z2": .15, "n": 1, "m": 3,
    }
    assert "traveling_wave" not in payload["solenoids"][0]["field_table"]
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setattr(simulation_io, "SIMULATION_DATA_PATH", str(runs))
    request = simulation_io.SimulationInput.model_validate_json(json.dumps(payload))
    ini = request.write_to_disk()
    for number, cavity in enumerate(request.cavities, 1):
        filename = f"TWS_C{number}_E.dat"
        assert cavity.File_Efield == filename
        assert f"File_Efield({number}) = '{filename}'" in ini
        assert f"C_numb({number}) = 6" in ini
        assert FieldTable.from_csv(Path(request.run_dir) / filename) == FieldTable.from_csv(source_map)
    restored = simulation_io.SimulationInput.model_validate(converter.convert_input(Path(request.input_filename)))
    assert restored.to_ini() == ini
    assert restored.cavities[0].field_table == request.cavities[0].field_table


@pytest.fixture
def aperture_input(tmp_path):
    (tmp_path / "aperture.dat").write_text("0 5\n.1 5\n.1 2\n.2 2\n")
    path = tmp_path / "apertures.in"
    path.write_text("""
&NEWRUN Distribution='beam.ini' /
&APERTURE LApert=.true.
    File_Aperture(9)='aperture.dat', A_pos(9)=1, A_xoff(9)=1D-3
    File_Aperture(4)='CIR', Ap_Z1(4)=.02, Ap_Z2(4)=.021
    Ap_GR(4,4)=3, Ap_GR(4,1)=0, Ap_GR(4,3)=2, Ap_GR(4,2)=1
    File_Aperture(3)='rAD', Ap_Z1(3)=.1, Ap_Z2(3)=.11, Ap_R(3)=-2
    File_Aperture(5)='Scr_X', Ap_Z1(5)=.2, Ap_Z2(5)=.21, Ap_R(5)=-1
    File_Aperture(6)='Scr_Y', Ap_Z1(6)=.3, Ap_Z2(6)=.31, Ap_R(6)=1
    File_Aperture(7)='Col_X', Ap_Z1(7)=.4, Ap_Z2(7)=.41, Ap_R(7)=2
    File_Aperture(8)='Col_Y', Ap_Z1(8)=.5, Ap_Z2(8)=.51, Ap_R(8)=3
    A_yoff(8)=.002, A_xrot(8)=.003, A_yrot(8)=.004, A_zrot(8)=.005
/
""")
    return path


def test_aperture_conversion_and_complete_disk_round_trip(aperture_input, tmp_path, monkeypatch):
    payload = converter.convert_input(aperture_input)
    apertures = payload["apertures"]
    assert [a["type"] for a in apertures] == ["RAD", "Cir", "Scr_X", "Scr_Y", "Col_X", "Col_Y", "table"]
    assert apertures[0]["radius"] == -2
    assert apertures[1]["grid_radii"] == [0, 1, 2, 3]
    assert apertures[-1]["aperture_table"] == {"z": [0, .1, .1, .2], "radius": [5, 5, 2, 2]}
    assert apertures[-1]["x_offset"] == .001
    assert apertures[-2]["xy_rotation"] == .005
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setattr(simulation_io, "SIMULATION_DATA_PATH", str(runs))
    request = simulation_io.SimulationInput.model_validate_json(json.dumps(payload))
    ini = request.write_to_disk()
    # Sorting moves the circular grid to index 1, and its second indices survive.
    assert "Ap_GR(1,4) = 3.0" in ini
    assert "File_Aperture(7) = 'A7.dat'" in ini
    restored = simulation_io.SimulationInput.model_validate(converter.convert_input(Path(request.input_filename)))
    assert restored.to_ini() == ini
    assert restored.apertures[-1].aperture_table == request.apertures[-1].aperture_table


def test_aperture_file_relocation(aperture_input):
    aperture_input.write_text(aperture_input.read_text().replace("'aperture.dat'", "'/container/aperture.dat'"))
    payload = converter.convert_input(aperture_input, field_map_dir=aperture_input.parent)
    assert payload["apertures"][-1]["aperture_table"]["radius"] == [5, 5, 2, 2]


@pytest.mark.parametrize("section", ["", "&APERTURE LApert=F, File_Aperture(1)='missing.dat' /"])
def test_disabled_or_absent_apertures_skip_unused_tables(tmp_path, section):
    path = tmp_path / "run.in"
    path.write_text("&NEWRUN Distribution='beam.ini' /\n" + section)
    assert converter.convert_input(path)["apertures"] == []


@pytest.mark.parametrize("section, message", [
    ("LApert=T", "no aperture settings"),
    ("LApert=1", "logical value"),
    ("File_Aperture='RAD'", "explicit aperture index"),
    ("Ap_R(1)=2", "must name a table"),
    ("Ap_GR(1)=2", "aperture and radius indices"),
    ("Ap_GR(1,41)=2", "at most 40 radii"),
    ("File_Aperture(1)='Cir', Ap_GR(1,2)=1", "consecutive from 1"),
    ("File_Aperture(1)='RAD', SE_d0(1)=1", "not supported by the REST API"),
])
def test_unrepresentable_apertures_fail_explicitly(tmp_path, section, message):
    path = tmp_path / "run.in"
    path.write_text("&NEWRUN Distribution='beam.ini' /\n&APERTURE " + section + " /")
    with pytest.raises(converter.ConversionError, match=message):
        converter.convert_input(path)


@pytest.mark.parametrize("text, message", [
    ("&APERTURE Ap_GR(1 2)=1 /", "expected"),
    ("&APERTURE Ap_GR(1,0)=1 /", "positive integer"),
    ("&APERTURE Ap_GR(1,1.5)=1 /", "positive integer"),
    ("&APERTURE Ap_GR(1,1,1)=1 /", "expected"),
    ("&APERTURE Ap_GR(1,1)=1, Ap_GR(1,1)=2 /", "Duplicate assignment"),
    ("&APERTURE Ap_R(1,1)=1 /", "Only &APERTURE.Ap_GR"),
    ("&CAVITY Phi(1,2)=1 /", "Only &APERTURE.Ap_GR"),
])
def test_invalid_multidimensional_indices_are_rejected(text, message):
    with pytest.raises(converter.ConversionError, match=message):
        converter.parse_namelists(text)


def test_aperture_cli_output_is_api_ready(aperture_input):
    result = subprocess.run([sys.executable, str(SCRIPT), str(aperture_input)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(aperture_input.with_name("simulation_in.json").read_text())
    assert payload["apertures"][1]["grid_radii"] == [0, 1, 2, 3]


def test_global_rf_phase_import(astra_input, monkeypatch, tmp_path):
    astra_input.write_text(astra_input.read_text().replace('&CAVITY', '&CAVITY\n Phi(0) = -37.18'))
    payload = converter.convert_input(astra_input)
    assert payload['run_specs']['global_rf_phase_shift'] == -37.18
    assert len(payload['cavities']) == 2
    monkeypatch.setattr(simulation_io, 'SIMULATION_DATA_PATH', str(tmp_path))
    request = simulation_io.SimulationInput.model_validate(payload)
    assert 'Phi(0) = -37.18' in request.write_to_disk()
