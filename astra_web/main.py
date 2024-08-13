import os, glob, typing, orjson
from shutil import rmtree
from datetime import datetime
from shortuuid import uuid
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import ORJSONResponse
from .utils import default_filename, GENERATOR_DATA_PATH, SIMULATION_DATA_PATH
from .auth.auth_schemes import api_key_auth
from .generator.schemas.io import GeneratorInput, GeneratorOutput
from .generator.schemas.particles import Particles
from .simulation.schemas.io import SimulationInput, SimulationOutput
from .generator.generator import write_input_file, process_generator_input, read_output_file, read_particle_file
from .simulation.simulation import process_simulation_input, load_emittance_output, load_simulation_output


tags_metadata = [
    {"name": "particles", "description": "All CRUD methods for particle distributions. Distributions are generated \
                                         by ASTRA generator binary."},
    {"name": "simulations", "description": "All CRUD methods for beam dynamics simulations. Simulations are run \
                                           by ASTRA binary."},
]


app = FastAPI(
    title="ASTRA WebAPI",
    description="This is an API wrapper for the ASTRA simulation code developed \
                 by K. Floettmann at DESY Hamburg. For more information, refer to the official \
                 [website](https://www.desy.de/~mpyflo/).",
    contact={
        "name": "Alexander Klemps",
        "email": "alexander.klemps@tuhh.de",
    },
    root_path=os.getenv("SERVER_ROOT_PATH", ""),
    openapi_tags=tags_metadata,
    default_response_class=ORJSONResponse
)


@app.post("/particles", dependencies=[Depends(api_key_auth)], tags=['particles'])
def generate_particle_distribution(generator_input: GeneratorInput) -> GeneratorOutput:
    """
    Description to be done
    """
    input_ini = write_input_file(generator_input)
    run_output = process_generator_input(generator_input)
    particle_output = read_output_file(generator_input)

    return GeneratorOutput(
        gen_id=generator_input.gen_id,
        particles=particle_output,
        run_output=run_output,
        input_ini=input_ini
    )


@app.put('/particles/{gen_id}', dependencies=[Depends(api_key_auth)], tags=['particles'])
def upload_particle_distribution(data: Particles, gen_id: str | None = None) -> dict:
    if gen_id is None: gen_id = f"{datetime.now().strftime('%Y-%m-%d')}-{uuid()[:8]}"
    path = default_filename(gen_id) + '.ini'
    if os.path.exists(path): os.remove(path)

    data.to_csv(path)
    return {"gen_id": gen_id}


@app.get('/particles/{gen_id}', dependencies=[Depends(api_key_auth)], tags=['particles'])
def download_particle_distribution(gen_id: str) -> Particles | None:
    """
    Returns a specific particle distribution on the requested server depending
    on the given filename.
    """
    path = default_filename(gen_id) + '.ini'
    if os.path.exists(path):
        return Particles.from_csv(path)
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item '{gen_id}' not found."
        )


@app.get('/particles', dependencies=[Depends(api_key_auth)], tags=['particles'])
def list_available_particle_distributions() -> list[str]:
    """
    Returns a list of all existing particle distributions on the requested server.
    """
    files = glob.glob(f"{GENERATOR_DATA_PATH}/*.ini")
    files = list(map(lambda p: p.split("/")[-1].split(".ini")[0], files))

    return sorted(files)


@app.delete('/particles/{gen_id}', dependencies=[Depends(api_key_auth)], tags=['particles'])
async def delete_particle_distribution(gen_id: str) -> None:
    path = default_filename(gen_id) + '.ini'
    if os.path.exists(path): os.remove(path)


@app.put('/simulations', dependencies=[Depends(api_key_auth)], tags=['simulations'])
async def run_simulation(simulation_input: SimulationInput) -> dict:
    simulation_input.write_to_disk()
    output = process_simulation_input(simulation_input)

    return {'output': output, 'sim_id': simulation_input.sim_id}


@app.post('/simulations', dependencies=[Depends(api_key_auth)], tags=['simulations'])
async def run_simulation_and_return_results(simulation_input: SimulationInput) -> SimulationOutput:
    input_ini = simulation_input.write_to_disk()
    output = process_simulation_input(simulation_input)
    x_table, y_table, z_table = load_emittance_output(simulation_input.run_dir)
    particle_paths = [simulation_input.run_specs.Distribution] + sorted(glob.glob(f"{simulation_input.run_dir}/run.*[0-9].001"), key=lambda s: s.split(".")[1])
    particles = [read_particle_file(path) for path in particle_paths]

    return SimulationOutput(
        sim_id=simulation_input.sim_id,
        input_ini=input_ini,
        run_output=output,
        particles=particles,
        emittance_x=x_table,
        emittance_y=y_table,
        emittance_z=z_table,
    )


@app.get('/simulations', dependencies=[Depends(api_key_auth)], tags=['simulations'])
def list_available_particle_distributions() -> list[str]:
    """
    Returns a list of all existing simulations on the requested server.
    """
    files = glob.glob(f"{SIMULATION_DATA_PATH}/*")
    files = list(map(lambda p: p.split("/")[-1], files))

    return sorted(files)


@app.get("/simulations/{sim_id}", dependencies=[Depends(api_key_auth)], tags=['simulations'])
def download_simulation_results(sim_id: str) -> SimulationOutput | None:
    """
        Returns the output of a specific ASTRA simulation on the requested server depending
        on the given ID.
        """
    path = os.path.abspath(f"{SIMULATION_DATA_PATH}/{sim_id}")
    if os.path.exists(path):
        return load_simulation_output(path, sim_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation '{sim_id}' not found."
        )


@app.delete('/simulations/{sim_id}', dependencies=[Depends(api_key_auth)], tags=['simulations'])
async def delete_simulation(sim_id: str) -> None:
    path = default_filename(f"{SIMULATION_DATA_PATH}/{sim_id}")
    if os.path.exists(path): rmtree(path)