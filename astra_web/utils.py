import os
from pathlib import Path
import re
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
    # Match filenames, rather than splitting full paths (run names can contain dots).
    directory = Path(SIMULATION_DATA_PATH) / sim_id
    return [str(path) for path in sorted(directory.glob("run.*.001"),
                                         key=lambda p: p.name)
            if re.fullmatch(r"run\.\d+\.001", path.name)]


def load_particle_snapshots(sim_id: str) -> pd.DataFrame:
    archive = Path(SIMULATION_DATA_PATH) / sim_id / "snapshots.parquet"
    if archive.exists():
        return pd.read_parquet(archive)

    # Older runs with a custom run_dir were not packed. Read their raw outputs
    # without deleting or modifying them. No snapshots is valid for PhaseS=false
    # or a run that stopped before its first output checkpoint.
    from astra_web.generator.schemas.particles import Particles
    frames = []
    for path in _particle_paths(sim_id):
        frame = pd.read_csv(path, sep=r"\s+", names=list(Particles.model_fields))
        frame["snapshot_z"] = int(Path(path).name.split(".")[1])
        frames.append(frame)
    if frames:
        return pd.concat(frames, ignore_index=True)
    return pd.DataFrame(columns=[*Particles.model_fields, "snapshot_z"])


def final_particle_snap(snapshots: pd.DataFrame):
    last_snapshot = snapshots[snapshots["snapshot_z"] == snapshots["snapshot_z"].max()].reset_index(drop=True)
    last_snapshot.drop("snapshot_z", inplace=True, axis=1)

    return last_snapshot
