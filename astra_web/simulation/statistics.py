import numpy as np
from astra_web.generator.schemas.particles import Particles
from astra_web.simulation.schemas.io import StatisticsInput, StatisticsOutput


C = 299792458
M0 = 9.10938356e-31

def get_statistics(statistics_input: StatisticsInput, particles: Particles) -> StatisticsOutput:
    return StatisticsOutput(
        z_pos=particles.z[0],
        slice_emittances=slice_emittance(particles, statistics_input.n_slices),
        sim_id=statistics_input.sim_id
    )

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

