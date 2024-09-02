import numpy as np
import json
from pmd_beamphysics import ParticleGroup
from astra_web.generator.schemas.particles import Particles
from astra_web.simulation.schemas.io import StatisticsInput, StatisticsOutput
from astra_web.utils import SIMULATION_DATA_PATH

C = 299792458
M0 = 9.10938356e-31


def get_statistics(statistics_input: StatisticsInput, particles: Particles) -> StatisticsOutput:
    with open(f"{SIMULATION_DATA_PATH}/{statistics_input.sim_id}/input.json", 'r') as f:
        sim_input = json.load(f)

    return StatisticsOutput(
        z_pos=particles.z[0],
        inputs=sim_input,
        sim_id=statistics_input.sim_id,
        slice_emittances=sl_emittance(particles.to_pmd(), statistics_input.n_slices),
        particle_count=len(particles.x),
        active_particle_count=sum(particles.active_particles())
    )


def sl_emittance(particle_group: ParticleGroup, n_slice):
    slice_data = particle_group.slice_statistics("norm_emit_x", "norm_emit_y", n_slice=n_slice)
    slice_zs = (slice_data['mean_z'] - particle_group.z[0]) * 1e3
    emittances = np.sqrt(slice_data["norm_emit_x"] * slice_data["norm_emit_y"]) * 1e6

    return list(map(tuple, np.vstack([slice_zs, emittances]).T))


def slice_emittance(particles: Particles, n_slices: 20) -> list[tuple[float, float]]:
    x, px, y, py, z = active_data(particles)
    z_min = np.min(z); z_max = np.max(z)
    dz = (z_max - z_min) / n_slices

    eps = []
    for i in range(n_slices):
        idx = np.logical_and(z < z_min + (i + 1) * dz, z > z_min + i * dz)
        eps_x = projected_emittance(x[idx], px[idx])
        eps_y = projected_emittance(y[idx], py[idx])
        slice_center = (z_min + (i + 0.5) * dz - z[0]) * 1e3 # mm
        eps.append((slice_center, np.sqrt(eps_x * eps_y) * 1e6))

    return eps


def active_data(particles: Particles):
    active = particles.active_particles
    x = np.array(particles.x)[active]
    px = np.array(particles.px)[active]
    y = np.array(particles.y)[active]
    py = np.array(particles.py)[active]
    z = np.array(particles.z)[active]
    z[1:] = z[0] + z[1:]

    return x, px, y, py, z



def projected_emittance(x, p) -> float:
    p_ = p * 5.36e-28 # kg*m/s
    x2 = np.mean(x**2) - np.mean(x)**2
    px2 = np.mean(p_**2) - np.mean(p_)**2
    xpx = np.mean(x*p_) - np.mean(x) * np.mean(p_)

    eps = 1/(M0*C) * np.sqrt(abs(x2*px2 - xpx**2))

    return eps

