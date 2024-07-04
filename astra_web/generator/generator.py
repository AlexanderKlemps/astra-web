import os
from subprocess import run
from astra_web.utils import get_env_var, default_filename
from .schemas.io import GeneratorInput
from .schemas.particles import Particles


ASTRA_GENERATOR_BINARY_PATH = get_env_var("ASTRA_GENERATOR_BINARY_PATH")


def write_input_file(generator_input: GeneratorInput) -> str:
    ini_content = generator_input.to_ini()
    with open(generator_input.input_filename, "w") as input_file:
        input_file.write(ini_content)

    return ini_content


def process_generator_input(generator_input: GeneratorInput) -> str:
    raw_process_output = run([ASTRA_GENERATOR_BINARY_PATH, generator_input.input_filename], capture_output=True).stdout
    decoded_process_output = raw_process_output.decode()
    output_file_name = default_filename(generator_input.gen_id) + ".out"
    with open(output_file_name, "w") as file:
        file.write(decoded_process_output)

    return decoded_process_output


def read_particle_file(filepath):
    if os.path.exists(filepath):
        return Particles.from_csv(filepath)
    else:
        return None


def read_output_file(generator_input: GeneratorInput) -> Particles:
    filepath = default_filename(generator_input.gen_id) + ".ini"

    return read_particle_file(filepath)

