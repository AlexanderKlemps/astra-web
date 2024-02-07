import os
from fastapi import FastAPI, Depends
from .auth.auth_schemes import api_key_auth
from .generator.schemas import GeneratorInput, GeneratorOutput
from .simulation.schemas import SimulationInput, SimulationOutput
from .generator.generator import write_input_file, process_generator_input, read_output_file, read_particle_file
from .simulation.simulation import process_simulation_input

app = FastAPI(
    title="ASTRA WebAPI",
    description="This is an API wrapper for the ASTRA simulation code developed \
                 by K. Floettmann at DESY Hamburg. For more information, refer to the official \
                 [website](https://www.desy.de/~mpyflo/).",
    contact={
        "name": "Alexander Klemps",
        "email": "alexander.klemps@tuhh.de",
    },
    root_path=os.getenv("SERVER_ROOT_PATH", "")
)


@app.post("/generate", dependencies=[Depends(api_key_auth)])
def generate(generator_input: GeneratorInput) -> GeneratorOutput:
    """
    PUT SOME NICE DESCRIPTION HERE
    """
    input_ini = write_input_file(generator_input)
    process_generator_input(generator_input)
    process_output = read_output_file(generator_input)
    process_output.input_ini = input_ini

    return process_output


@app.post('/simulate', dependencies=[Depends(api_key_auth)])
def simulate(simulation_input: SimulationInput) -> SimulationOutput:
    input_ini = simulation_input.write_to_disk()
    output = process_simulation_input(simulation_input)

    return SimulationOutput(
        timestamp=simulation_input.timestamp,
        input_ini=input_ini,
        run_output=output,
        particles=read_particle_file(f"{simulation_input.run_dir}/run.0100.001")
    )

