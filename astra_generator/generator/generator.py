import os.path
from subprocess import run
from astra_generator.utils import get_env_var, default_filename
from .schemas import GeneratorInput, GeneratorOutput, Particles
import pandas as pd


ASTRA_GENERATOR_BINARY_PATH = get_env_var("ASTRA_GENERATOR_BINARY_PATH")


def write_input_file(generator_input: GeneratorInput) -> str:
    ini_content = generator_input.to_ini()
    with open(generator_input.input_filename, "w") as input_file:
        input_file.write(ini_content)

    return ini_content


def process_generator_input(generator_input: GeneratorInput) -> str:
    raw_process_output = run([ASTRA_GENERATOR_BINARY_PATH, generator_input.input_filename], capture_output=True).stdout
    decoded_process_output = raw_process_output.decode()
    output_file_name = default_filename(generator_input.creation_time) + ".out"
    with open(output_file_name, "w") as file:
        file.write(decoded_process_output)

    return decoded_process_output


def read_particle_file(filepath):
    if os.path.exists(filepath):
        df = pd.read_fwf(filepath, names=list(Particles.model_fields.keys()))
        return Particles(**df.to_dict("list"))
    else:
        return None


def read_output_file(generator_input: GeneratorInput) -> Particles:
    filepath = default_filename(generator_input.creation_time) + ".ini"

    return read_particle_file(filepath)

