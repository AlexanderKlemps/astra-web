import os, glob
from datetime import datetime
from fastapi import FastAPI, Depends
from .utils import default_filename, GENERATOR_DATA_PATH
from .auth.auth_schemes import api_key_auth
from .generator.schemas import GeneratorInput, GeneratorOutput, Particles
from .simulation.schemas import SimulationInput, SimulationOutput
from .generator.generator import write_input_file, process_generator_input, read_output_file, read_particle_file
from .simulation.simulation import process_simulation_input, load_emittance_output

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
def generate_particle_distribution(generator_input: GeneratorInput) -> GeneratorOutput:
    """
    Description to be done
    """
    input_ini = write_input_file(generator_input)
    run_output = process_generator_input(generator_input)
    particle_output = read_output_file(generator_input)

    return GeneratorOutput(
        timestamp=generator_input.creation_time,
        particles=particle_output,
        run_output=run_output,
        input_ini=input_ini
    )


@app.post('/simulate', dependencies=[Depends(api_key_auth)])
def run_simulation(simulation_input: SimulationInput) -> SimulationOutput:
    input_ini = simulation_input.write_to_disk()
    output = process_simulation_input(simulation_input)
    x_table, y_table, z_table = load_emittance_output(simulation_input.run_dir)
    particle_paths = [simulation_input.run_specs.Distribution] + sorted(
        glob.glob(f"{simulation_input.run_dir}/run.0*.001"),
        key=lambda s: s.split(".")[2]
    )
    particles = [read_particle_file(path) for path in particle_paths]

    return SimulationOutput(
        timestamp=simulation_input.timestamp,
        input_ini=input_ini,
        run_output=output,
        particles=particles,
        emittance_x=x_table,
        emittance_y=y_table,
        emittance_z=z_table,
    )

@app.post('/particles/{filename}', dependencies=[Depends(api_key_auth)])
def upload_particle_distribution(data: Particles, filename: str | None = None) -> dict:
    if filename is None: filename = str(datetime.now().timestamp())
    data.to_csv(default_filename(filename) + '.ini')

    return {"filename": filename}

@app.get('/particles/{filename}', dependencies=[Depends(api_key_auth)])
def download_particle_distribution(filename: str) -> Particles | None:
    """
    Returns a specific particle distribution on the requested server depending
    on the given filename.
    """
    return Particles.from_csv(default_filename(filename) + '.ini')

@app.get('/particles', dependencies=[Depends(api_key_auth)])
def list_available_particle_distributions() -> list[str]:
    """
    Returns a list of all existing particle distributions on the requested server.
    """
    files = glob.glob(f"{GENERATOR_DATA_PATH}/*.ini")
    files = list(map(lambda p: p.split("/")[-1].split(".ini")[0], files))
    return sorted(files)
