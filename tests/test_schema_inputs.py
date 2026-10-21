import json

import pytest
from pydantic import TypeAdapter, ValidationError

from astra_web.generator.schemas.io import GeneratorInput
from astra_web.simulation.schemas import io as simulation_io
from astra_web.simulation.schemas.io import SimulationOutputSpecification
from astra_web.simulation.schemas.modules import Aperture, Cavity, Quadrupole, Solenoid
from astra_web.simulation.schemas.run import SimulationRunSpecifications
from astra_web.simulation.schemas.space_charge import SpaceCharge


TABLE = {"z": [0, 1], "v": [0, 1]}
RENAMES = [
    (SimulationRunSpecifications, {}, "H_min", "min_time_step", "start_time", .0001),
    (SimulationRunSpecifications, {}, "H_max", "max_time_step", "end_time", .002),
    (Cavity, {"id": 1, "field_table": TABLE}, "C_pos", "z_offset", "z_0", .2),
    (Solenoid, {"id": 1, "field_table": TABLE}, "S_pos", "z_offset", "z_0", .2),
    (Quadrupole, {"id": 1, "effective_length": .1}, "Q_pos", "z_center", "z_0", .2),
    (Quadrupole, {"id": 1, "z_center": 1}, "Q_length", "effective_length", "q_len", .1),
    (Quadrupole, {"id": 1, "effective_length": .1, "z_center": 1},
     "Q_K", "focusing_strength", "q_focus", -2.),
    (Quadrupole, {"id": 1, "effective_length": .1, "z_center": 1},
     "Q_Bore", "fringe_taper_length", "bore_radius", .02),
]


@pytest.mark.parametrize("model, base, field, public, legacy, value", RENAMES)
def test_public_legacy_and_native_names_produce_identical_astra_input(model, base, field, public, legacy, value):
    instances = [model.model_validate({**base, key: value}) for key in (public, legacy, field)]
    assert all(getattr(instance, field) == value for instance in instances)
    assert len({instance.to_ini() for instance in instances}) == 1
    properties = model.model_json_schema()["properties"]
    assert public in properties
    assert legacy not in properties


@pytest.mark.parametrize("model, base, field, public, legacy, value", RENAMES)
def test_alias_conflicts_fail_and_equal_duplicates_do_not_mutate_input(model, base, field, public, legacy, value):
    with pytest.raises(ValidationError, match="Conflicting values"):
        model.model_validate({**base, public: value, legacy: value + 1})
    with pytest.raises(ValidationError, match="Conflicting values"):
        model.model_validate({**base, public: value, field: value + 1})
    payload = {**base, public: value, legacy: value, field: value}
    original = json.dumps(payload)
    instance = model.model_validate(payload)
    assert getattr(instance, field) == value
    assert json.dumps(payload) == original


@pytest.mark.parametrize("precision, reference", [(False, True), (True, False), (False, False), (True, True)])
def test_output_switches_are_independent(precision, reference):
    output = SimulationOutputSpecification(high_accuracy=precision, generate_reference_output=reference)
    assert output.High_res is precision
    assert output.RefS is reference
    ini = output.to_ini()
    assert f"High_res = {str(precision).lower()}" in ini
    assert f"RefS = {str(reference).lower()}" in ini
    assert SimulationOutputSpecification(high_accuracy=False).RefS is True


@pytest.mark.parametrize("model, payload, absent_fields", [
    (SimulationRunSpecifications,
     {"sim_id": None, "Z_min": None, "particle_file_name": None, "bunch_charge": None},
     ["sim_id", "Z_min", "particle_file_name", "Qbunch"]),
    (SpaceCharge,
     {"z_trans": None, "3D_x_grid_size": None, "3D_y_grid_size": None, "3D_z_grid_size": None},
     ["z_trans", "Nxf", "Nyf", "Nzf"]),
    (Solenoid, {"id": 1, "field_table": TABLE, "z_offset": None, "max_field_strength": None},
     ["S_pos", "MaxB"]),
    (GeneratorInput,
     {"rms_energy_spread": None, "rms_dist_px": None, "rms_bunch_size_y": None, "rms_dist_py": None,
      "rms_bunch_size_z": None, "sig_t": None, "x_emittance": None, "y_emittance": None,
      "gaussian_cutoff_x": None, "gaussian_cutoff_y": None, "gaussian_cutoff_z": None,
      "flattop_z_length": None, "flattop_rise_z": None, "flattop_time_length": None, "flattop_rise_time": None},
     ["sig_Ekin", "sig_px", "sig_y", "sig_py", "sig_z", "sig_clock", "Nemit_x", "Nemit_y",
      "C_sig_x", "C_sig_y", "C_sig_z", "Lz", "rz", "Lt", "rt"]),
])
def test_optional_nulls_are_accepted_and_omitted_from_astra(model, payload, absent_fields):
    instance = model.model_validate_json(json.dumps(payload))
    ini = instance.to_ini()
    written_keys = {line.split('=', 1)[0].strip().split('(', 1)[0]
                    for line in ini.splitlines() if '=' in line}
    for name in absent_fields:
        assert getattr(instance, name) is None
        assert name not in written_keys
    if model is SpaceCharge:
        assert instance.L2D_3D is False
    if model is SimulationRunSpecifications:
        assert instance.Distribution.endswith("/example.ini")


@pytest.mark.parametrize("model", [Cavity, Solenoid])
@pytest.mark.parametrize("payload", [{}, {"field_table": None}])
def test_field_maps_cannot_be_missing_or_null(model, payload):
    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize("payload", [
    {}, {"z_center": 1}, {"effective_length": .1},
    {"effective_length": None, "z_center": 1},
    {"effective_length": .1, "z_center": None},
])
def test_quadrupole_geometry_cannot_be_missing_or_null(payload):
    with pytest.raises(ValidationError):
        Quadrupole.model_validate(payload)


@pytest.mark.parametrize("model, payload", [
    (Cavity, {"field_table": TABLE, "z_offset": None}),
    (Cavity, {"field_table": TABLE, "max_field_strength": None}),
    (SimulationRunSpecifications, {"min_time_step": None}),
    (SimulationOutputSpecification, {"generate_reference_output": None}),
    (SpaceCharge, {"use_space_charge": None}),
    (GeneratorInput, {"particle_count": None}),
])
def test_nonnullable_inputs_do_not_turn_null_into_a_default(model, payload):
    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize("model, payload", [
    (Cavity, {"field_table": TABLE, "max_field_strenght": 60}),
    (Solenoid, {"field_table": TABLE, "z_offest": 1}),
    (Quadrupole, {"effective_length": .1, "z_center": 1, "focussing_strength": 2}),
    (SimulationRunSpecifications, {"min_timestep": .0001}),
    (SpaceCharge, {"use_space_chrage": True}),
])
def test_unknown_input_names_are_rejected(model, payload):
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model.model_validate(payload)


def test_invalid_nested_null_does_not_create_a_run_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(simulation_io, "SIMULATION_DATA_PATH", str(tmp_path))
    with pytest.raises(ValidationError):
        simulation_io.SimulationInput.model_validate({"cavities": [{"field_table": None}]})
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("model", [
    GeneratorInput, Cavity, Solenoid, Quadrupole, Aperture,
    SimulationRunSpecifications, SpaceCharge, SimulationOutputSpecification,
])
def test_every_declared_default_matches_its_type_and_constraints(model):
    for field in model.model_fields.values():
        if not field.is_required() and field.default_factory is None:
            TypeAdapter(field.rebuild_annotation()).validate_python(field.default)


def test_native_attribute_names_preserve_requested_values():
    cavity = Cavity(field_table=TABLE, MaxE=58.1)
    assert cavity.MaxE == 58.1
    assert SimulationRunSpecifications(H_max=.002).H_max == .002
    assert SimulationOutputSpecification(High_res=False, RefS=True).RefS is True


@pytest.mark.parametrize("name", ["check_reference_particle", "check_ref_part"])
def test_reference_particle_check_can_be_disabled_explicitly(name):
    run = SimulationRunSpecifications.model_validate({name: False})
    assert run.check_ref_part is False
    assert "check_ref_part = false" in run.to_ini()
    assert "check_ref_part = true" in SimulationRunSpecifications().to_ini()
    with pytest.raises(ValidationError):
        SimulationRunSpecifications.model_validate({name: None})
