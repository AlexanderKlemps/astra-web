from subprocess import run
from .utils import get_env_var, default_filename
from .schemas import GeneratorInput, GeneratorOutput, Particles
import pandas as pd

ASTRA_GENERATOR_BINARY_PATH = get_env_var("ASTRA_GENERATOR_BINARY_PATH")


def write_input_file(generator_input: GeneratorInput) -> None:
    with open(generator_input.input_filename, "w") as input_file:
        input_file.write(generator_input.to_ini())


def process_generator_input(generator_input: GeneratorInput) -> str:
    raw_process_output = run([ASTRA_GENERATOR_BINARY_PATH, generator_input.input_filename], capture_output=True).stdout
    decoded_process_output = raw_process_output.decode()
    output_file_name = default_filename(generator_input.creation_time) + ".out"
    with open(output_file_name, "w") as file:
        file.write(decoded_process_output)

    return decoded_process_output


def read_output_file(generator_input: GeneratorInput) -> GeneratorOutput:
    filepath = default_filename(generator_input.creation_time) + ".ini"
    df = pd.read_fwf(filepath, names=list(Particles.model_fields.keys()))

    return GeneratorOutput(timestamp=generator_input.creation_time, particles=Particles(**df.to_dict("list")))
