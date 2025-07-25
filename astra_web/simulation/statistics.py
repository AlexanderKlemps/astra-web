import numpy as np
import json
from pmd_beamphysics import ParticleGroup
from pmd_beamphysics.statistics import particle_twiss_dispersion
from astra_web.generator.schemas.particles import Particles
from astra_web.simulation.schemas.io import StatisticsInput, StatisticsOutput
from astra_web.utils import SIMULATION_DATA_PATH

C = 299792458
M0 = 9.10938356e-31


def get_statistics(sim_id: str, n_slices: int, particles: Particles) -> StatisticsOutput:
    with open(f"{SIMULATION_DATA_PATH}/{sim_id}/input.json", 'r') as f:
        sim_input = json.load(f)

    particle_group = particles.to_pmd(only_active=True)
    try:
        slice_data = sl_emittance(particle_group, n_slices)
        z_pos = particle_group.avg("z")
        ptp_z = particle_group.ptp("z")
    except (ZeroDivisionError, ValueError) as e:
        print(f"Calculation of slice statistics for sim {sim_id} raised {type(e)}. Message: {e}")
        z_pos = particles.z[0]
        ptp_z = max(particles.z) - min(particles.z)
        slice_data = {}

    return StatisticsOutput(
        z_pos=z_pos,
        ptp_z=ptp_z * 1e3,
        inputs=sim_input,
        sim_id=sim_id,
        particle_counts={
            'total': len(particles.x),
            'active': int(sum(particles.active_particles)),
            'lost': int(sum(particles.lost_particles))},
        **slice_data
    )

def mismatch(p_group, slice_data):
    twiss = particle_twiss_dispersion(p_group, plane="x")
    twiss.update(particle_twiss_dispersion(p_group, plane="y"))
    betas = np.sqrt(slice_data["twiss_beta_y"] * slice_data["twiss_beta_x"])
    alphas = np.sign(slice_data["twiss_alpha_x"])*np.sign(slice_data["twiss_alpha_y"])*np.sqrt(np.abs(slice_data["twiss_alpha_x"] * slice_data["twiss_alpha_y"]))
    gammas = np.sqrt(slice_data["twiss_gamma_x"] * slice_data["twiss_gamma_y"])
    alpha_0 = np.sign(twiss['alpha_x'])*np.sign(twiss["alpha_y"])*np.sqrt(np.abs(twiss['alpha_x'] * twiss["alpha_y"]))
    beta_0 = np.sqrt(twiss['beta_x'] * twiss["beta_y"])
    gamma_0 = np.sqrt(twiss['gamma_x'] * twiss["gamma_y"])

    return (np.vstack([alphas, betas, gammas]).tolist(),
            (alpha_0, beta_0, gamma_0, np.sqrt(twiss["norm_emit_x"] * twiss["norm_emit_y"]) * 1e6),
            0.5 * (beta_0*gammas - 2*alpha_0*alphas + gamma_0*betas))

def sl_emittance(particle_group: ParticleGroup, n_slice):
    slice_data = particle_group.slice_statistics("norm_emit_x", "norm_emit_y", "twiss_xy", n_slice=n_slice)
    slice_zs = (slice_data['mean_z'] - particle_group.avg("z")) * 1e3
    slice_densities = slice_data['density']
    emittances = np.sqrt(slice_data["norm_emit_x"] * slice_data["norm_emit_y"]) * 1e6
    slice_twiss, bunch_twiss, slice_mismatch = mismatch(particle_group, slice_data)

    return {
        "slice_zs": slice_zs,
        "slice_emittances": emittances,
        "slice_densities": slice_densities,
        "slice_mismatch": slice_mismatch,
        "slice_twiss": slice_twiss,
        "bunch_twiss": bunch_twiss
    }



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

