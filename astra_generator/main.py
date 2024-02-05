import os
from fastapi import FastAPI, Depends
from .auth.auth_schemes import api_key_auth
from .generator.schemas import GeneratorInput, GeneratorOutput
from .simulation.schemas import SimulationInput
from .generator.generator import write_input_file, process_generator_input, read_output_file

app = FastAPI(root_path=os.getenv("SERVER_ROOT_PATH", ""))


@app.post("/generate", dependencies=[Depends(api_key_auth)])
def generate(generator_input: GeneratorInput) -> GeneratorOutput:
    write_input_file(generator_input)
    process_generator_input(generator_input)
    process_output = read_output_file(generator_input)

    return process_output


@app.post('/simulate', dependencies=[Depends(api_key_auth)])
def simulate(simulation_input: SimulationInput) -> str:
    return simulation_input.to_ini()
