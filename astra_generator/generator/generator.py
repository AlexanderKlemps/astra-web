from subprocess import run
from .utils import get_env_var, output_filename, particle_outputfile
from .schemas import Input, ParticleOutput, Output
import pandas as pd

ASTRA_GENERATOR_BINARY_PATH = get_env_var("ASTRA_GENERATOR_BINARY_PATH")


def write_input_file(generator_input: Input) -> None:
    with open(generator_input.input_filename(), "w") as input_file:
        input_file.write(generator_input.to_ini())

    return


def process_generator_input(generator_input: Input) -> str:
    raw_process_output = run([ASTRA_GENERATOR_BINARY_PATH, generator_input.input_filename()], capture_output=True).stdout
    decoded_process_output = raw_process_output.decode()
    with open(output_filename(generator_input.creation_time()), "w") as file:
        file.write(decoded_process_output)

    return decoded_process_output


def read_output_file(generator_input: Input) -> Output:
    filepath = particle_outputfile(generator_input.creation_time())
    keys = list(ParticleOutput.model_fields.keys())
    df = pd.read_fwf(filepath, names=keys)
    output = Output(
        timestamp=generator_input.creation_time(),
        particles=ParticleOutput(**df.to_dict("list"))
    )

    return output
