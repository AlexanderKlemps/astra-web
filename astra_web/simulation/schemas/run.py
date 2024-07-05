from pydantic import BaseModel, Field, computed_field
from astra_web.utils import GENERATOR_DATA_PATH
from astra_web.decorators.decorators import ini_exportable

@ini_exportable
class SimulationRunSpecifications(BaseModel):
    run_dir: str = Field(
        default=None,
        description='Name of the directory the simulation will be executed in.',
        exclude=True
    )

    Version: int = Field(
        default=4
    )

    @computed_field(
        return_type=str,
        description='Run name for protocol',
        repr=True
    )
    @property
    def Head(self) -> str:
        return f"Simulation run with initial particle distribution {self.particle_file_name}"

    thread_num: int = Field(
        default=1,
        gt=1,
        description='The number of concurrent threads used per simulation.',
        exclude=True
    )

    timeout: int = Field(
        default=600,
        description='The timeout for the simulation run. Simulation terminated if timeout time is exceeded.',
        exclude=True
    )

    RUN: int = Field(
        default=1,
        validation_alias='run_number',
        description='The run_number is used as extension for all generated output files.'
    )
    particle_file_name: str = Field(
        default=None,
        description='Name of a particle file generated with the /generate endpoint of this API.',
        exclude=True
    )

    @computed_field(
        return_type=str,
        description='Name of the file containing the initial particle distribution to be used.',
        repr=True
    )
    @property
    def Distribution(self) -> str:
        file_name = 'example.ini'
        if self.particle_file_name is not None:
            file_name = self.particle_file_name + ".ini"
        return f"{GENERATOR_DATA_PATH}/{file_name}"

    Qbunch: float = Field(
        default=None,
        validation_alias='bunch_charge',
        description='Bunch charge in [nC]. Scaling is active if bunch_charge != 0.',
        json_schema_extra={'format': 'Unit: [nC]'}
    )
    Q_Schottky: float = Field(
        default=0.0,
        validation_alias='schottky_coefficient',
        description='Linear variation of the bunch charge with the field on the cathode. Scaling is \
                     active if Q_Schottky != 0.',
        json_schema_extra={'format': 'Unit: [nC*m/MV]'}
    )
    XYrms: float = Field(
        default=-1.0,
        validation_alias='rms_laser_spot_size',
        description='Horizontal and vertical rms beam size. Scaling is active if rms_laser_spot_size > 0.0.',
        json_schema_extra={'format': 'Unit: [mm]'}
    )
    Trms: float = Field(
        default=-1.0,
        validation_alias='rms_emission_time',
        description='RMS emission time of the bunch. Scaling is active if rms_emission_time > 0.0.',
        json_schema_extra={'format': 'Unit: [ns]'}
    )
    H_min: float = Field(
        default=0.0,
        validation_alias='start_time',
        description='Minimum time step for the Runge-Kutta integration and min. time step for the \
                     space charge calculation.',
        json_schema_extra={'format': 'Unit: [ns]'},
    )
    H_max: float = Field(
        default=0.001,
        validation_alias='end_time',
        description='Maximum time step for the Runge-Kutta integration.',
        json_schema_extra={'format': 'Unit: [ns]'},
    )
    Max_step: int = Field(
        default=100000,
        validation_alias='max_iteration',
        description='Safety termination: after Max_step Runge_Kutta steps the run is terminated.'
    )
    Z_Cathode: float = Field(
        default=0.0,
        validation_alias='z_cathode',
        description='Position of the cathode for the calculation of the mirror charge.',
        json_schema_extra={'format': 'Unit: [m]'}
    )
    Track_All: bool = Field(
        default=True,
        validation_alias='track_all_particles',
        description='If false, only the reference particle will be tracked.'
    )
    Auto_Phase: bool = Field(
        default=True,
        validation_alias='auto_phase',
        description='If true, the RF phases will be set relative to the phase with maximum energy gain.'
    )

    def to_ini(self):
        return "&NEWRUN" + self._to_ini() + "/"