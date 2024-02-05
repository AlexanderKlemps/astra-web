from pydantic import BaseModel, Field, ConfigDict, computed_field
from astra_generator.decorators.decorators import ini_exportable
from .utils import default_filename
from datetime import datetime
from aenum import MultiValueEnum


class Distribution(str, MultiValueEnum):
    gauss = "gaussian", "gauss", "g"
    uniform = "uniform", "u"
    plateau = "plateau", "p"
    inverted = "inverted", "i"
    r = "radial_uniform"
    isotropic = "isotropic"
    FD_300 = "fd_300"


@ini_exportable
class GeneratorInput(BaseModel):
    # Model config
    model_config = ConfigDict(use_enum_values=True)
    # Internal attributes
    _timestamp: str | None = str(datetime.now()).replace(" ", "_")

    # Attributes relevant for dump to ASTRA input file
    # Aliases correspond to possibly externally used keywords
    # attribute names correspond to ASTRA interface
    @computed_field(return_type=str)
    @property
    def FNAME(self) -> str:
        return f"'{default_filename(self._timestamp)}.ini'"

    @property
    def input_filename(self) -> str:
        return self.FNAME[1:-2]

    Add: bool | None = False
    N_add: int | None = 0
    IPart: int = Field(default=100, validation_alias='particle_count')
    Species: str = Field(default='electrons', validation_alias='particle_type')
    Probe: bool = Field(default=True, validation_alias='generate_probe_particles')
    Noise_reduc: bool = Field(default=True, validation_alias='quasi_random')
    Q_total: float = Field(default=1.0, validation_alias='total_charge')
    Cathode: bool = Field(default=True, validation_alias='time_spread')
    High_res: bool = Field(default=True, validation_alias='high_accuracy')
    Ref_zpos: float | None = 0.0E0
    Dist_z: Distribution = Field(default='gauss', validation_alias='dist_z')
    Dist_pz: Distribution = Field(default='gauss', validation_alias='dist_pz')
    Dist_x: Distribution = Field(default='gauss', validation_alias='dist_x')
    Dist_px: Distribution = Field(default='gauss', validation_alias='dist_px')
    Dist_y: Distribution = Field(default='gauss', validation_alias='dist_y')
    Dist_py: Distribution = Field(default='gauss', validation_alias='dist_py')
    cor_Ekin: float | None = 0.0E0
    cor_px: float | None = 0.0E0
    cor_py: float | None = 0.0E0
    Ref_Ekin: float | None = None
    sig_Ekin: float | None = None
    sig_x: float | None = None
    sig_y: float | None = None
    sig_z: float | None = None
    C_sig_z: float | None = None
    Nemit_x: float | None = None
    Nemit_y: float | None = None

    @property
    def creation_time(self):
        return self._timestamp

    def to_ini(self) -> str:
        return f"&INPUT{self._to_ini()}/"


class Particles(BaseModel):
    x: list[float] = Field(default=[], description='List of particle x values [m].')
    y: list[float] = Field(default=[], description='List of particle y values [m].')
    z: list[float] = Field(default=[], description='List of particle z values [m].')
    px: list[float] = Field(default=[], description='List of particle px values in [eV/c].')
    py: list[float] = Field(default=[], description='List of particle py values in [eV/c].')
    pz: list[float] = Field(default=[], description='List of particle pz values in [eV/c].')
    clock: list[float] | None = []  # unit [ns]
    macro_charge: list[float] = Field(
        default=[],
        description='List of particle macro charges in [nC].'
    )
    particle_index: list[int] | None = []
    status_flag: list[int] | None = []


class GeneratorOutput(BaseModel):
    timestamp: str
    particles: Particles

