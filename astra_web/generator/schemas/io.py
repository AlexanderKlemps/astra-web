from datetime import datetime
from typing import Optional
from shortuuid import uuid
from pydantic import BaseModel, Field, ConfigDict, computed_field
from astra_web.decorators.decorators import ini_exportable
from astra_web.utils import default_filename
from .enums import Distribution, ParticleType
from .particles import Particles


@ini_exportable
class GeneratorInput(BaseModel):
    # Model config
    model_config = ConfigDict(use_enum_values=True)
    # Internal attributes
    _gen_id: str | None = None

    # Attributes relevant for dump to ASTRA input file
    # Aliases correspond to possibly externally used keywords
    # attribute names correspond to ASTRA interface
    @computed_field(return_type=str)
    @property
    def FNAME(self) -> str:
        return f"{default_filename(self._gen_id)}.ini"

    @property
    def input_filename(self) -> str:
        return self.FNAME[:-1]

    Add: bool | None = False
    N_add: int | None = 0
    IPart: int = Field(
        default=100,
        validation_alias='particle_count',
        description='Number of particles to be generated.'
    )
    Species: ParticleType = Field(
        default='electrons',
        validation_alias='particle_type',
        description='Species of particles to be generated.'
    )
    Probe: bool = Field(
        default=True,
        validation_alias='generate_probe_particles',
        description='If true, 6 probe particles are generated.'
    )
    Noise_reduc: bool = Field(
        default=True,
        validation_alias='quasi_random',
        description='If true, particle coordinates are generated quasi-randomly following a Hammersley sequence.'
    )
    Cathode: bool = Field(
        default=True,
        validation_alias='time_spread',
        description='If true the particles will be generated with a time spread rather than with a \
                     spread in the longitudinal position.'
    )
    High_res: bool = Field(
        default=True,
        validation_alias='high_accuracy',
        description='If true, the particle distribution is saved with increased accuracy.'
    )
    Q_total: float = Field(
        default=1.0,
        validation_alias='total_charge',
        description='Total charge of the particles, equally distributed on the number of particles.',
        json_schema_extra={'format': 'Unit: [nC]'},
    )
    Dist_z: Distribution = Field(
        default='gauss',
        validation_alias='dist_z',
        description='Specifies the type of the longitudinal particle distribution.'
    )
    Dist_pz: Distribution = Field(
        default='gauss',
        validation_alias='dist_pz',
        description='Specifies the longitudinal energy and momentum distribution, respectively.'
    )
    Dist_x: Distribution = Field(
        default='gauss',
        validation_alias='dist_x',
        description='Specifies the transverse particle distribution in the horizontal direction.'
    )
    Dist_px: Distribution = Field(
        default='gauss',
        validation_alias='dist_px',
        description='Specifies the transverse momentum distribution in the horizontal direction.'
    )
    Dist_y: Distribution = Field(
        default='gauss',
        validation_alias='dist_y',
        description='Specifies the transverse particle distribution in the vertical direction.'
    )
    Dist_py: Distribution = Field(
        default='gauss',
        validation_alias='dist_py',
        description='Specifies the transverse momentum distribution in the vertical direction.'
    )
    cor_Ekin: float = Field(
        default=0.0,
        validation_alias='cor_energy_spread',
        description='Correlated energy spread.'
    )
    cor_px: float = Field(
        default=0.0,
        description='correlated beam divergence in the horizontal direction.',
        json_schema_extra={'format': 'Unit: [mrad]'},
    )
    cor_py: float = Field(
        default=0.0,
        description='Correlated beam divergence in the vertical direction.',
        json_schema_extra={'format': 'Unit: [mrad]'},
    )
    Ref_Ekin: float = Field(
        default=0.0,
        validation_alias='reference_kinetic_energy',
        description='initial kinetic energy of the reference particle',
        json_schema_extra={'format': 'Unit: [keV]'},
    )
    Ref_zpos: float = Field(
        default=0.0,
        validation_alias='z_0_ref',
        description='z position of the reference particle, i.e. the longitudinal bunch position.',
        json_schema_extra={'format': 'Unit: [m]'},
    )
    sig_Ekin: float = Field(
        default=0.0,
        validation_alias="rms_energy_spread",
        description='RMS value of the energy spread.',
        json_schema_extra={'format': 'Unit: [keV]'},
    )
    sig_x: float = Field(
        default=1.0,
        validation_alias='rms_bunch_size_x',
        description='RMS bunch size in the horizontal direction.',
        json_schema_extra={'format': 'Unit: [mm]'},
    )
    sig_px: float = Field(
        default=0.0,
        validation_alias='rms_dist_px',
        description='RMS value of the horizontal momentum distribution.',
        json_schema_extra={'format': 'Unit: [eV/c]'},
    )
    sig_y: float = Field(
        default=1.0,
        validation_alias='rms_bunch_size_y',
        description='RMS bunch size in the vertical direction.',
        json_schema_extra={'format': 'Unit: [mm]'},
    )
    sig_py: float = Field(
        default=0.0,
        validation_alias='rms_dist_py',
        description='RMS value of the vertical momentum distribution.',
        json_schema_extra={'format': 'Unit: [eV/c]'},
    )
    sig_z: float = Field(
        default=0.0,
        validation_alias='rms_bunch_size_z',
        description='RMS value of the bunch length.',
        json_schema_extra={'format': 'Unit: [mm]'},
    )
    sig_clock: float = Field(
        default=1e-3,
        validation_alias='sig_t',
        description='RMS rms value of the emission time, i.e. the bunch length if generated from a cathode.',
        json_schema_extra={'format': 'Unit: [ns]'},
    )
    Nemit_x: float = Field(
        default=0.0,
        validation_alias='x_emittance',
        description='Normalized transverse emittance in the horizontal direction.',
        json_schema_extra={'format': 'Unit: [pi*mrad*mm]'},
    )
    Nemit_y: float = Field(
        default=0.0,
        validation_alias='y_emittance',
        description='Normalized transverse emittance in the vertical direction.',
        json_schema_extra={'format': 'Unit: [pi*mrad*mm]'},
    )
    C_sig_x: float = Field(
        default=0.0,
        validation_alias='gaussian_cutoff_x',
        description='Cuts off a Gaussian longitudinal distribution at C_sig_z times sig_z.'
    )
    C_sig_y: float = Field(
        default=0.0,
        validation_alias='gaussian_cutoff_y',
        description='Cuts off a Gaussian longitudinal distribution at C_sig_z times sig_z.'
    )
    C_sig_z: float = Field(
        default=0.0,
        validation_alias='gaussian_cutoff_z',
        description='Cuts off a Gaussian longitudinal distribution at C_sig_z times sig_z.'
    )
    Lz: float = Field(
        default=0.0,
        validation_alias='flattop_z_length',
        description='Length of the bunch.',
        json_schema_extra={'format': 'Unit: [mm]'},
    )
    rz: float = Field(
        default=0.0,
        validation_alias='flattop_rise_z',
        description='Rise time of a bunch with flattop distribution.',
        json_schema_extra={'format': 'Unit: [mm]'},
    )
    Lt: float = Field(
        default=0.0,
        validation_alias='flattop_time_length',
        description='Length of the bunch with flattop distribution.',
        json_schema_extra={'format': 'Unit: [ns]'},
    )
    rt: float = Field(
        default=0.0,
        validation_alias='flattop_rise_time',
        description='Rise time of a bunch with flattop distribution.',
        json_schema_extra={'format': 'Unit: [ns]'},
    )

    @property
    def gen_id(self):
        return self._gen_id

    def to_ini(self) -> str:
        return f"&INPUT{self._to_ini()}/"

    def model_post_init(self, __context) -> None:
        self._gen_id = f"{datetime.now().strftime('%Y-%m-%d')}-{uuid()[:8]}"


class GeneratorOutput(BaseModel):
    gen_id: str
    particles: Optional[Particles]
    input_ini: str | None = ""
    run_output: str

