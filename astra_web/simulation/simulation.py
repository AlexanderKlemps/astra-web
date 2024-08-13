import os
import glob
import pandas as pd
from subprocess import run
from .schemas.io import SimulationInput, SimulationOutput
from .schemas.tables import XYEmittanceTable, ZEmittanceTable
from astra_web.utils import get_env_var
from astra_web.generator.generator import read_particle_file

ASTRA_BINARY_PATH = get_env_var("ASTRA_BINARY_PATH")


def process_simulation_input(simulation_input: SimulationInput) -> str:
    raw_process_output = run(
        _run_command(simulation_input),
        cwd=simulation_input.run_dir,
        capture_output=True,
        timeout=simulation_input.run_specs.timeout
    ).stdout

    terminal_output = raw_process_output.decode()
    output_file_name = f"{simulation_input.run_dir}/run.out"
    with open(output_file_name, "w") as file:
        file.write(terminal_output)

    return terminal_output


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
    particle_paths = sorted(
        glob.glob(f"{path}/run.*[0-9].001"),
        key=lambda s: s.split(".")[1]
    )
    particles = [read_particle_file(path) for path in particle_paths]
    return SimulationOutput(
        sim_id=sim_id,
        input_ini=input_ini,
        run_output=output,
        particles=particles,
        emittance_x=x_table,
        emittance_y=y_table,
        emittance_z=z_table,
    )