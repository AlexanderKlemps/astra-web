from subprocess import run
from .schemas import SimulationInput, XYEmittanceTable, ZEmittanceTable
from astra_web.utils import get_env_var
import pandas as pd
import os

ASTRA_SIMULATION_BINARY_PATH = get_env_var("ASTRA_SIMULATION_BINARY_PATH")


def process_simulation_input(simulation_input: SimulationInput) -> str:
    raw_process_output = run([
        ASTRA_SIMULATION_BINARY_PATH,
        simulation_input.input_filename],
        cwd=simulation_input.run_dir,
        capture_output=True).stdout

    terminal_output = raw_process_output.decode()
    output_file_name = f"{simulation_input.run_dir}/run.out"
    with open(output_file_name, "w") as file:
        file.write(terminal_output)

    return terminal_output


def load(file_path: str, model_cls):
    try:
        if os.path.exists(file_path):
            df = pd.read_fwf(file_path, names=list(model_cls.model_fields.keys()))
            return model_cls(**df.to_dict("list"))
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
