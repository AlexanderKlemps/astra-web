import os, glob, typing, orjson
from shutil import rmtree
from datetime import datetime
from shortuuid import uuid
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import ORJSONResponse
from fastapi.exceptions import RequestValidationError
from .execution import run_job, check_mpi_processes
from .errors import request_validation_error_handler
from .utils import default_filename, GENERATOR_DATA_PATH, SIMULATION_DATA_PATH
from .auth.auth_schemes import api_key_auth
from .generator.schemas.particles import Particles
from .generator.schemas.io import GeneratorInput, GeneratorOutput
from .simulation.schemas.io import StatisticsInput, StatisticsOutput
from .simulation.schemas.io import SimulationInput, SimulationOutput
from .generator.generator import write_input_file, process_generator_input, read_output_file
from .simulation.simulation import process_simulation_input, load_simulation_output
from .simulation.statistics import get_statistics

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
app.add_exception_handler(RequestValidationError, request_validation_error_handler)


@app.get("/healthz", include_in_schema=False)
async def health():
    return {"status": "ok"}


@app.post("/particles", dependencies=[Depends(api_key_auth)], tags=['particles'])
async def generate_particle_distribution(generator_input: GeneratorInput) -> GeneratorOutput:
    return await run_job(_generate_particle_distribution, generator_input)


def _generate_particle_distribution(generator_input: GeneratorInput) -> GeneratorOutput:
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
    check_mpi_processes(simulation_input)
    return await run_job(_run_simulation, simulation_input)


def _run_simulation(simulation_input: SimulationInput) -> dict:
    simulation_input.write_to_disk()
    output = process_simulation_input(simulation_input)

    return {'output': output, 'sim_id': simulation_input.sim_id}


@app.post('/simulations', dependencies=[Depends(api_key_auth)], tags=['simulations'])
async def run_simulation_and_return_results(simulation_input: SimulationInput) -> SimulationOutput:
    check_mpi_processes(simulation_input)
    return await run_job(_run_simulation_and_return_results, simulation_input)


def _run_simulation_and_return_results(simulation_input: SimulationInput) -> SimulationOutput:
    simulation_input.write_to_disk()
    process_simulation_input(simulation_input)
    return load_simulation_output(simulation_input.run_dir, simulation_input.sim_id)


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


@app.post('/simulations/statistics', dependencies=[Depends(api_key_auth)], tags=['simulations'])
def statistics(statistics_input: StatisticsInput) -> list[StatisticsOutput]:
    stats = []
    for sim_id in statistics_input.sim_ids:
        stats.append(get_statistics(sim_id, statistics_input.n_slices))

    return stats
