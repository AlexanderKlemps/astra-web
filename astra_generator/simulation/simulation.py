from subprocess import run
from .schemas import SimulationInput
from astra_generator.utils import get_env_var

ASTRA_SIMULATION_BINARY_PATH = get_env_var("ASTRA_SIMULATION_BINARY_PATH")


def process_simulation_input(simulation_input: SimulationInput) -> str:
    raw_process_output = run([
        ASTRA_SIMULATION_BINARY_PATH,
        simulation_input.input_filename],
        cwd=simulation_input.run_dir,
        capture_output=True).stdout

    output = raw_process_output.decode()
    output_file_name = f"{simulation_input.run_dir}/{simulation_input.timestamp}" + ".out"
    with open(output_file_name, "w") as file:
        file.write(output)

    return output

