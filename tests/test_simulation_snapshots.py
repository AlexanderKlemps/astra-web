from pathlib import Path
from subprocess import CompletedProcess

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from astra_web import main, utils
from astra_web.simulation import simulation, statistics
from astra_web.simulation.schemas import io


SNAPSHOT = "0 0 1 0 0 1000000 0 -0.001 1 5\n0.001 0 0.01 0 0 10 0 -0.001 1 5\n"


@pytest.fixture
def storage(tmp_path, monkeypatch):
    for module in (io, simulation, utils, main, statistics):
        monkeypatch.setattr(module, 'SIMULATION_DATA_PATH', str(tmp_path))
    return tmp_path


def make_request(name=None):
    return io.SimulationInput(run_specs={'sim_id': name}, output_specs={
        'z_stop': 13.51, 'distribution_checkpoint_num': 1,
        'emittance_checkpoint_num': 1,
    })


@pytest.mark.parametrize('name', ['1pCTripleOnCrest', 'beam.scan.1', None])
def test_run_id_snapshot_archive_and_get_agree(storage, monkeypatch, name):
    request = make_request(name)
    if name is not None:
        assert request.sim_id == name
    assert Path(request.run_dir) == storage / request.sim_id

    def execute(*args, **kwargs):
        assert Path(kwargs['cwd']) == storage / request.sim_id
        (Path(kwargs['cwd']) / 'run.1351.001').write_text(SNAPSHOT)
        return CompletedProcess(args[0], 0, b'finished', b'')
    monkeypatch.setattr(simulation, 'run', execute)
    result = main._run_simulation(request)
    assert result['sim_id'] == request.sim_id
    assert (Path(request.run_dir) / 'snapshots.parquet').exists()
    assert not (Path(request.run_dir) / 'run.1351.001').exists()
    response = main.download_simulation_results(result['sim_id'])
    assert len(response.particles) == 1
    assert response.particles[0].pz == [1000000.0, 10.0]
    assert request.sim_id in main.list_available_particle_distributions()


def test_post_returns_packed_particles(storage, monkeypatch):
    request = make_request('post-run')
    def execute(*args, **kwargs):
        (Path(kwargs['cwd']) / 'run.1351.001').write_text(SNAPSHOT)
        return CompletedProcess(args[0], 0, b'finished', b'')
    monkeypatch.setattr(simulation, 'run', execute)
    response = main._run_simulation_and_return_results(request)
    assert response.sim_id == 'post-run'
    assert len(response.particles) == 1
    assert len(response.particles[0].x) == 2


def test_old_unpacked_custom_run_remains_readable(storage):
    request = make_request('legacy')
    request.write_to_disk()
    directory = Path(request.run_dir)
    (directory / 'run.out').write_text('finished')
    (directory / 'run.1351.001').write_text(SNAPSHOT)
    response = main.download_simulation_results('legacy')
    assert response.particles[0].z == [1.0, .01]
    assert (directory / 'run.1351.001').exists()
    assert not (directory / 'snapshots.parquet').exists()


def test_missing_snapshots_allow_get_but_not_statistics(storage):
    request = make_request('no-snapshots')
    request.write_to_disk()
    (Path(request.run_dir) / 'run.out').write_text('stopped before first checkpoint')
    assert main.download_simulation_results('no-snapshots').particles == []
    with pytest.raises(HTTPException) as error:
        statistics.get_statistics('no-snapshots', 10)
    assert error.value.status_code == 409
    assert 'No particle snapshots' in error.value.detail['message']


def test_existing_run_is_not_overwritten(storage):
    request = make_request('unique')
    marker = Path(request.run_dir) / 'preserve'
    marker.write_text('existing results')
    with pytest.raises(HTTPException) as error:
        make_request('unique')
    assert error.value.status_code == 409
    assert marker.read_text() == 'existing results'


@pytest.mark.parametrize('name', ['', '.', '..', '../outside', '/tmp/outside', 'a/b', 'a\\b'])
def test_sim_id_is_a_single_safe_id(storage, name):
    with pytest.raises(ValidationError):
        make_request(name)
    assert not list(storage.iterdir())


def test_failed_packing_preserves_all_raw_files(storage, monkeypatch):
    request = make_request('packing-failure')
    directory = Path(request.run_dir)
    raw = [directory / 'run.0000.001', directory / 'run.1351.001']
    for path in raw:
        path.write_text(SNAPSHOT)
    real_read = simulation.pd.read_csv
    def read(path, **kwargs):
        if Path(path) == raw[1]:
            raise ValueError('unreadable snapshot')
        return real_read(path, **kwargs)
    monkeypatch.setattr(simulation.pd, 'read_csv', read)
    with pytest.raises(ValueError, match='unreadable snapshot'):
        simulation.squash_particle_files(request.sim_id)
    assert all(path.exists() for path in raw)
    assert not (directory / 'snapshots.parquet').exists()
    assert not list(directory.glob('*.tmp'))


@pytest.mark.parametrize('payload', [
    {'run_dir': 'legacy-name'},
    {'sim_id': 'legacy-name', 'run_dir': 'legacy-name'},
])
def test_legacy_id_alias(storage, payload):
    request = io.SimulationInput(run_specs=payload)
    assert request.sim_id == 'legacy-name'
    assert request.run_specs.sim_id == 'legacy-name'
    assert Path(request.run_dir) == storage / 'legacy-name'
    assert 'sim_id' not in request.run_specs.to_ini()
    assert 'run_dir' not in request.run_specs.to_ini()


def test_conflicting_id_aliases_do_not_create_a_directory(storage):
    with pytest.raises(ValidationError, match='Conflicting values for sim_id'):
        io.SimulationInput(run_specs={'sim_id': 'first', 'run_dir': 'second'})
    assert not list(storage.iterdir())


def test_openapi_uses_sim_id():
    properties = io.SimulationRunSpecifications.model_json_schema()['properties']
    assert 'sim_id' in properties
    assert 'run_dir' not in properties
