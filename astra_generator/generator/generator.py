from subprocess import run
from .utils import get_env_var, default_filename, output_filename, outputfile_exists, particle_outputfile
from .schemas import Particle, Input

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


def transform_line(line: str) -> Particle:
    split_line = line.replace("\n", "").split(" ")
    filtered_split = list(filter(None, split_line))
    particle_data = dict(zip(Particle.__fields__.keys(), filtered_split))

    return Particle(**particle_data)


def read_output_file(timestamp: str) -> list[Particle]:
    output = []
    if outputfile_exists(timestamp):
        with open(particle_outputfile(timestamp), 'r') as output_file:
            parsed_output = output_file.readlines()

        output = list(map(transform_line, parsed_output))

    return output



