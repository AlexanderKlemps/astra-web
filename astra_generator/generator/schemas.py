from pydantic import BaseModel
from .utils import output_filename, default_filename
from datetime import datetime


class Input(BaseModel):
    _timestamp: str | None = str(datetime.now()).replace(" ", "_")
    FNAME: str | None = default_filename(_timestamp) + ".ini"
    Add: bool | None = False
    N_add: int | None = 0
    IPart: int | None = 100
    Species: str | None = 'electrons'
    Probe: bool | None = True
    Noise_reduc: bool | None = True
    Q_total: float | None = 1.0
    Cathode: bool | None = True
    Ref_zpos: float | None = 0.0E0
    #Ref_Ekin = 2.0E0
    Dist_z: str | None = 'g'  # g, p, u, i, r, 2, inverted
    Dist_pz: str | None = 'g'
    #sig_z = 1.0E0,
    #sig_Ekin = 1.5,
    Dist_x: str | None = 'g'
    Dist_px: str | None = 'g'
    Dist_y: str | None = 'g'
    Dist_py: str | None = 'g'
    #sig_x: float
    #Nemit_x = 1.0E0
    #sig_y = 0.75E0
    #Nemit_y = 1.0E0
    #C_sig_z = 2.0
    cor_Ekin: float | None = 0.0E0
    cor_px: float | None = 0.0E0
    cor_py: float | None = 0.0E0

    def input_filename(self):
        return default_filename(self._timestamp) + ".in"

    def creation_time(self):
        return self._timestamp

    def to_ini(self) -> str:
        ini_output = (self.json(indent=4, exclude_none=True)
                      # replace string value double quotation marks by single quotation marks
                      .replace(": \"", ": '").replace("\",", "',")
                      # replace key value delimiters ':', remove key double quotes
                      .replace("\": ", "=").replace("\"", ""))

        # replace enclosing brackets
        ini_output = "&INPUT" + ini_output[1:-1] + "/"

        return ini_output


class Particle(BaseModel):
    x: float  # unit [m]
    y: float  # unit [m]
    z: float  # unit [m]
    px: float  # unit [eV/c]
    py: float  # unit [eV/c]
    pz: float  # unit [eV/c]
    clock: float | None = None  # unit [ns]
    macro_charge: float | None = None  # unit [nC]
    particle_index: int | None = None
    status_flag: int | None = None


class Output(BaseModel):
    particles: list[Particle]
