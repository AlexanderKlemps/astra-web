import glob
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
import pyarrow as pa
import optparse
import numpy as np
from multiprocessing import Pool

PARTICLE_KEYS = ["x", "y", "z", "px", "py", "pz", "t_clock", "macro_charge", "species", "status"]
SIMULATION_DATA_PATH = "simulation"


def _particle_paths(sim_id):
    return sorted(glob.glob(f"{SIMULATION_DATA_PATH}/{sim_id}/run.*[0-9].001"), key=lambda s: s.split(".")[1])


def _squash_particle_files(sim_id: str):
    particle_files = [Path(s) for s in _particle_paths(sim_id)[1:]]
    writer = None

    for file in particle_files:
        df = pd.read_csv(file, sep=r"\s+", names=PARTICLE_KEYS, engine="python")
        df["snapshot_z"] = int(file.name.split(".")[1])
        table = pa.Table.from_pandas(df, preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(f"{SIMULATION_DATA_PATH}/{sim_id}/snapshots.parquet",
                                      table.schema, compression="zstd")
        writer.write_table(table)
        file.unlink()

    if writer:
        writer.close()

def squash_particle_files(sim_ids: list[str]):
    for sim_id in sim_ids:
        _squash_particle_files(sim_id)


if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option('-n', dest='n_threads', default=2, type=int)
    (options, args) = parser.parse_args()

    sim_ids = glob.glob1(SIMULATION_DATA_PATH, "*")

    # Create a pool with n_threads workers
    with Pool(options.n_threads) as pool:
        pool.map(_squash_particle_files, sim_ids)