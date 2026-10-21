import os
import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from subprocess import run, TimeoutExpired
import logging
import tempfile
from fastapi import HTTPException
from .schemas.io import SimulationInput, SimulationOutput
from .schemas.tables import XYEmittanceTable, ZEmittanceTable
from astra_web.utils import get_env_var, _particle_paths, SIMULATION_DATA_PATH, load_particle_snapshots
from ..generator.schemas.particles import Particles

ASTRA_BINARY_PATH = get_env_var("ASTRA_BINARY_PATH")


def link_initial_particle_distribution(simulation_input: SimulationInput):
    os.symlink(simulation_input.run_specs.Distribution,
               f"{simulation_input.run_dir}/run.0000.001")


def process_simulation_input(simulation_input: SimulationInput) -> str:
    output_path = Path(simulation_input.run_dir) / "run.out"
    error_path = Path(simulation_input.run_dir) / "run.err"

    def decode(value):
        return value.decode(errors="replace") if isinstance(value, bytes) else (value or "")

    def fail(message, stdout, stderr, status_code=500, returncode=None):
        output_path.write_text(decode(stdout))
        error_path.write_text(decode(stderr))
        logging.getLogger("uvicorn.error").error(
            "%s sim_id=%s returncode=%s; see run.out and run.err",
            message, simulation_input.sim_id, returncode,
        )
        raise HTTPException(status_code=status_code, detail={
            "message": message,
            "sim_id": simulation_input.sim_id,
            "returncode": returncode,
            "stderr": decode(stderr)[-8000:],
        })

    try:
        result = run(
            _run_command(simulation_input),
            cwd=simulation_input.run_dir,
            capture_output=True,
            timeout=simulation_input.run_specs.timeout,
        )
    except TimeoutExpired as exc:
        fail("ASTRA execution timed out", exc.stdout, exc.stderr, status_code=504)
    except OSError as exc:
        fail("Could not start ASTRA/MPI", "", str(exc))

    terminal_output = decode(result.stdout)
    output_path.write_text(terminal_output)
    error_path.write_text(decode(result.stderr))
    if result.returncode != 0:
        fail("ASTRA/MPI exited unsuccessfully", result.stdout, result.stderr,
             returncode=result.returncode)
    if not terminal_output.strip():
        fail("ASTRA/MPI returned no standard output", result.stdout, result.stderr,
             returncode=result.returncode)

    squash_particle_files(simulation_input.sim_id)
    return terminal_output


def squash_particle_files(sim_id: str):
    particle_files = [Path(s) for s in _particle_paths(sim_id)]
    if not particle_files:
        return

    archive = Path(SIMULATION_DATA_PATH) / sim_id / "snapshots.parquet"
    with tempfile.NamedTemporaryFile(dir=archive.parent, suffix=".parquet.tmp", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        writer = None
        try:
            for file in particle_files:
                df = pd.read_csv(file, sep=r"\s+", names=list(Particles.model_fields), engine="python")
                df["snapshot_z"] = int(file.name.split(".")[1])
                table = pa.Table.from_pandas(df, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(temporary_path, table.schema, compression="zstd")
                writer.write_table(table)
        finally:
            if writer is not None:
                writer.close()
        temporary_path.replace(archive)
    finally:
        temporary_path.unlink(missing_ok=True)
    # Keep all raw snapshots until the complete archive has been closed and published.
    for file in particle_files:
        file.unlink()


def _run_command(simulation_input: SimulationInput) -> list[str]:
    cmd = [_astra_binary(simulation_input), simulation_input.input_filename]

    if simulation_input.run_specs.thread_num > 1:
        cmd = ['mpirun', "-n", str(simulation_input.run_specs.thread_num)] + cmd
    return cmd


def _astra_binary(simulation_input: SimulationInput) -> str:
    binary = "astra"
    if simulation_input.run_specs.thread_num > 1:
        binary = "parallel_" + binary

    return f"{ASTRA_BINARY_PATH}/{binary}"


def load(file_path: str, model_cls):
    try:
        if os.path.exists(file_path):
            return model_cls.from_csv(file_path)
        else:
            return None
    except pd.errors.EmptyDataError:
        return None


def load_emittance_output(run_dir: str) -> list[XYEmittanceTable]:
    tables = []
    for coordinate in ['x', 'y', 'z']:
        file_name = f"{run_dir}/run.{coordinate.upper()}emit.001"
        model_cls = ZEmittanceTable if coordinate == 'z' else XYEmittanceTable
        tables.append(load(file_name, model_cls))

    return tables


def load_simulation_output(path: str, sim_id: str) -> SimulationOutput:
    x_table, y_table, z_table = load_emittance_output(path)
    with open(f"{path}/run.out", "r") as f:
        output = f.read()
    with open(f"{path}/run.in", "r") as f:
        input_ini = f.read()

    snapshots = load_particle_snapshots(sim_id)
    particles = [Particles(**snap.drop("snapshot_z", axis=1).to_dict("list")) for _, snap in snapshots.groupby("snapshot_z")]
    return SimulationOutput(
        sim_id=sim_id,
        input_ini=input_ini,
        run_output=output,
        particles=particles,
        emittance_x=x_table,
        emittance_y=y_table,
        emittance_z=z_table,
    )