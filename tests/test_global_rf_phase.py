import pytest
from pydantic import ValidationError
from astra_web.simulation.schemas import io
from astra_web.simulation.schemas.run import SimulationRunSpecifications


@pytest.mark.parametrize('phase', [None, 0, -40.5, 720.25])
def test_phase_exports_only_in_cavity(tmp_path, monkeypatch, phase):
    monkeypatch.setattr(io, 'SIMULATION_DATA_PATH', str(tmp_path))
    request = io.SimulationInput(run_specs={'global_rf_phase_shift': phase},
        cavities=[{'phase': 12.0, 'field_table': {'z': [0, 1], 'v': [0, 1]}}])
    text = request.write_to_disk()
    assert 'global_rf_phase_shift' not in text
    assert 'Phi(0)' not in request.run_specs.to_ini()
    assert request.run_specs.model_dump()['global_rf_phase_shift'] == phase
    assert 'Phi(1) = 12.0' in text
    if phase is None:
        assert 'Phi(0)' not in text
    else:
        assert text.count('Phi(0)') == 1
        assert f'Phi(0) = {float(phase)}' in text.split('&CAVITY')[1].split('/')[0]


@pytest.mark.parametrize('phase', [float('nan'), float('inf'), float('-inf'), 'bad'])
def test_invalid_phase(phase):
    with pytest.raises(ValidationError):
        SimulationRunSpecifications(global_rf_phase_shift=phase)


def test_omitted_phase():
    assert SimulationRunSpecifications().global_rf_phase_shift is None
