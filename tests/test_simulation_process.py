from subprocess import CompletedProcess, TimeoutExpired
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from astra_web.simulation import simulation


@pytest.fixture
def request_input(tmp_path):
    return SimpleNamespace(run_dir=str(tmp_path), sim_id="test-run",
                           input_filename="run.in",
                           run_specs=SimpleNamespace(thread_num=2, timeout=5))


@pytest.mark.parametrize("code,stdout,stderr", [
    (1, b"", b"not enough slots"),
    (0, b"", b"unexpected empty output"),
])
def test_failed_process_is_not_reported_as_success(monkeypatch, tmp_path, request_input,
                                                 code, stdout, stderr):
    def execute(command, **kwargs):
        assert command[:3] == ["mpirun", "-n", "2"]
        assert kwargs["capture_output"] is True
        return CompletedProcess(command, code, stdout, stderr)
    monkeypatch.setattr(simulation, "run", execute)
    monkeypatch.setattr(simulation, "squash_particle_files", lambda _: pytest.fail("processed failed run"))
    with pytest.raises(HTTPException) as error:
        simulation.process_simulation_input(request_input)
    assert error.value.status_code == 500
    assert error.value.detail["stderr"] == stderr.decode()
    assert error.value.detail["returncode"] == code
    assert (tmp_path / "run.err").read_bytes() == stderr


def test_success_keeps_stderr_and_processes_results(monkeypatch, tmp_path, request_input):
    monkeypatch.setattr(simulation, "run", lambda *a, **k: CompletedProcess(a[0], 0, b"finished", b"warning"))
    processed = []
    monkeypatch.setattr(simulation, "squash_particle_files", processed.append)
    assert simulation.process_simulation_input(request_input) == "finished"
    assert processed == ["test-run"]
    assert (tmp_path / "run.err").read_text() == "warning"


@pytest.mark.parametrize("exception,status", [
    (TimeoutExpired("mpirun", 5, output=b"partial", stderr=b"timeout details"), 504),
    (FileNotFoundError("mpirun missing"), 500),
])
def test_launch_errors_saved(monkeypatch, tmp_path, request_input, exception, status):
    def execute(*args, **kwargs):
        raise exception
    monkeypatch.setattr(simulation, "run", execute)
    with pytest.raises(HTTPException) as error:
        simulation.process_simulation_input(request_input)
    assert error.value.status_code == status
    assert (tmp_path / "run.err").read_text()
    if status == 504:
        assert (tmp_path / "run.out").read_text() == "partial"
