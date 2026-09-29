import numpy as np
import glob

if __name__ == "__main__":
    paths = glob.glob("simulation/*")
    all_macro_states = {}

    for path in paths:
        sim = path.split("/")[-1]
        sim_macro_state = np.load(path + "/run.macro_states.0000-0450.001.npy").astype(np.float32)
        all_macro_states[sim] = sim_macro_state

    np.savez_compressed("macro_states.f32.compressed.npz", **all_macro_states)