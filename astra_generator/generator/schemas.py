from pydantic import BaseModel, Field, ConfigDict
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
    FD_300 = "df_300"


class Input(BaseModel):
    # Model config
    model_config = ConfigDict(use_enum_values=True)
    # Internal attributes
    _timestamp: str | None = str(datetime.now()).replace(" ", "_")

    # Attributes relevant for dump to ASTRA input file
    # Aliases correspond to possibly externally used keywords
    # attribute names correspond to ASTRA interface
    FNAME: str | None = default_filename(_timestamp) + ".ini"
    Add: bool | None = False
    N_add: int | None = 0
    IPart: int = Field(default=100, validation_alias='particle_count')
    Species: str = Field(default='electrons', validation_alias='particle_type')
    Probe: bool = Field(default=True, validation_alias='generate_probe_particles')
    Noise_reduc: bool = Field(default=True, validation_alias='quasi_random')
    Q_total: float = Field(default=1.0, validation_alias='total_charge')
    Cathode: bool = Field(default=True, validation_alias='time_spread')
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

    def input_filename(self):
        return default_filename(self._timestamp) + ".in"

    def creation_time(self):
        return self._timestamp

    def to_ini(self) -> str:
        ini_output = (self.model_dump_json(indent=4, exclude_none=True)
                      # replace string value double quotation marks by single quotation marks
                      .replace(": \"", ": '").replace("\",", "',")
                      # replace key value delimiters ':', remove key double quotes
                      .replace("\": ", "=").replace("\"", ""))

        # replace enclosing brackets
        ini_output = "&INPUT" + ini_output[1:-1] + "/"

        return ini_output


class ParticleOutput(BaseModel):
    x: list[float]  # unit [m]
    y: list[float]  # unit [m]
    z: list[float]  # unit [m]
    px: list[float]  # unit [eV/c]
    py: list[float]  # unit [eV/c]
    pz: list[float]  # unit [eV/c]
    clock: list[float] | None = None  # unit [ns]
    macro_charge: list[float] | None = None  # unit [nC]
    particle_index: list[int] | None = None
    status_flag: list[int] | None = None


class Output(BaseModel):
    timestamp: str
    particles: ParticleOutput

