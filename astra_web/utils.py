import os
import glob
import pandas as pd
from dotenv import load_dotenv


def get_env_var(variable_name: str, default=None) -> str:
    if variable_name not in os.environ:
        load_dotenv("/")
        var = os.getenv(variable_name)
    else:
        var = os.environ[variable_name]

    if var is None: var = default

    return var


DATA_PATH = os.path.abspath(os.path.join(__file__, "../../"))
GENERATOR_DATA_PATH = f"{DATA_PATH}{get_env_var('GENERATOR_DATA_PATH', default='/data/generator')}"
SIMULATION_DATA_PATH = f"{DATA_PATH}{get_env_var('SIMULATION_DATA_PATH', default='/data/simulation')}"


def default_filename(timestamp) -> str:
    return os.path.join(GENERATOR_DATA_PATH, timestamp)


def _particle_paths(sim_id):
    return sorted(glob.glob(f"{SIMULATION_DATA_PATH}/{sim_id}/run.*[0-9].001"), key=lambda s: s.split(".")[1])


def load_particle_snapshots(sim_id:str) -> pd.DataFrame:
    return pd.read_parquet(f"{SIMULATION_DATA_PATH}/{sim_id}/snapshots.parquet")


def final_particle_snap(snapshots: pd.DataFrame):
    last_snapshot = snapshots[snapshots["snapshot_z"] == snapshots["snapshot_z"].max()].reset_index(drop=True)
    last_snapshot.drop("snapshot_z", inplace=True, axis=1)

    return last_snapshot
