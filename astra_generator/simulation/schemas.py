import os
from pydantic import BaseModel, Field, ConfigDict, computed_field, model_serializer
from datetime import datetime
from typing import Any, Optional
from astra_generator.generator.schemas import Particles
from astra_generator.decorators.decorators import ini_exportable
from astra_generator.utils import GENERATOR_DATA_PATH, SIMULATION_DATA_PATH
import pandas as pd
import numpy as np


class FieldTable(BaseModel):
    z: list[float] = Field(
        description='Longitudinal positions along z-axis.',
        json_schema_extra={'format': 'Unit: [m]'}
    )
    v: list[float] = Field(
        description='Field values at z positions in free units.',
        json_schema_extra={'format': 'Unit: free'}
    )

    def to_csv(self, file_name) -> None:
        pd.DataFrame({'z': self.z, "v": self.v}).to_csv(file_name, sep=" ", header=False, index=False)


class Module(BaseModel):
    @model_serializer
    def ser_model(self) -> dict[str, Any]:
        out_dict = dict()
        for key, val in self:
            if not self.model_fields[key].exclude == True and val is not None:
                out_dict[f'{key}({self.id})'] = val

        return out_dict


@ini_exportable
class Cavity(Module):
    id: int = Field(
        exclude=True,
        default=None,
        description="The ID of the cavity.")

    field_table: FieldTable = Field(
        exclude=True,
        default=None,
        description="Table containing lists of longitudinal positions z and corresponding \
                    field amplitudes v in free units.",
        json_schema_extra={'format': 'Unit: [m]'}
    )

    @computed_field(return_type=str)
    @property
    def File_Efield(self) -> str:
        return f"C{self.id}_E.dat"

    Nue: float = Field(
        default=1.3E0,
        validation_alias='frequency',
        description='Frequency of the RF field.',
        json_schema_extra={'format': 'Unit: [GHz]'}
    )
    C_pos: float = Field(
        default=0.0E0,
        validation_alias='z_0',
        description='Leftmost longitudinal cavity position.',
        json_schema_extra={'format': 'Unit: [m]'}
    )
    C_smooth: int = Field(
        default=10,
        validation_alias='smoothing_iterations',
        description='Number of iterations for smoothing of transverse field components.'
    )
    C_higher_order: bool = Field(
        default=True,
        validation_alias='higher_order',
        description='If true, field expansion extends to 3rd order, 1st order if false.'
    )
    Phi: float = Field(
        default=0.0E0,
        validation_alias='phase',
        description='Initial phase of the RF field.',
        json_schema_extra={'format': 'Unit: [deg]'}
    )
    MaxE: float = Field(
        default=130.0E0,
        validation_alias='max_field_strength',
        description='Maximum on-axis longitudinal amplitude of the RF field',
        json_schema_extra={'format': 'Unit: [MV/m] | [T]'}
    )

    def write_to_disk(self, path) -> None:
        if self.field_table is None:
            return
        self.field_table.to_csv(f"{path}/{self.File_Efield}")

    @property
    def z_0(self):
        return self.C_pos

    def ser_model(self) -> dict[str, Any]:
        out_dict = super().ser_model()
        out_dict[f'File_Efield({self.id})'] = self.File_Efield

        return out_dict


@ini_exportable
class Solenoid(Module):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: int = Field(
        default=None,
        exclude=True,
        description="The ID of the solenoid."
    )
    field_table: FieldTable = Field(
        default=None,
        exclude=True,
        description="Table containing lists of longitudinal positions z and corresponding \
                    field amplitudes v in free units.",
        json_schema_extra={'format': 'Unit: [m]'}
    )

    @computed_field(return_type=str)
    @property
    def File_Bfield(self) -> str:
        return f"S{self.id}_B.dat"

    S_pos: float = Field(
        default=None,
        validation_alias='z_0',
        description='Leftmost longitudinal solenoid position.',
        json_schema_extra={'format': 'Unit: [m]'},
    )
    S_smooth: int = Field(
        default=10,
        validation_alias='smoothing_iterations',
        description='Number of iterations for smoothing of transverse field components.'
    )
    MaxB: float = Field(
        default=None,
        validation_alias='max_field_strength',
        description='Maximum on-axis longitudinal amplitude of the magnetic field.',
        json_schema_extra={'format': 'Unit: [T]'}
    )

    @property
    def z_0(self):
        return self.S_pos

    def ser_model(self) -> dict[str, Any]:
        out_dict = super().ser_model()
        out_dict[f'File_Bfield({self.id})'] = self.File_Bfield

        return out_dict

    def write_to_disk(self, path) -> None:
        if self.field_table is None:
            return
        self.field_table.to_csv(f"{path}/{self.File_Bfield}")


@ini_exportable
class SpaceCharge(BaseModel):
    LSPCH: bool = Field(
        default=False,
        validation_alias='use_space_charge',
        description='Toggle whether to calculate space charge fields or not.'
    )
    z_trans: float = Field(
        default=None,
        description='Longitudinal position for automatic transition of 2D to 3D space charge\
                    calculation.',
        json_schema_extra={'format': 'Unit: [m]'},
    )
    Lmirror: bool = Field(
        default=True,
        validation_alias='use_mirror_charge',
        description='If true, mirror charges at the cathode are taken into account.'
    )
    Nrad: int = Field(
        gt=0,
        default=32,
        validation_alias='grid_cell_count',
        description='Number of grid cells in radial direction up to the bunch radius.'
    )
    Cell_var: float = Field(
        default=2.0,
        validation_alias='cell_size_scale',
        description='Variation of the cell height in radial direction. \
                    The innermost cell is cell_var times higher than the outermost cell'
    )
    Max_Scale: float = Field(
        default=0.05,
        validation_alias='max_scale',
        description='If one of the space charge scaling factors exceeds the limit 1± max_scale a new \
                    space charge calculation is initiated.'
    )
    Max_Count: int = Field(
        default=40,
        gt=0,
        validation_alias='max_scale_count',
        description='If the space charge field has been scaled max_scale_count times, a new \
                     space charge calculation is initiated.'
    )
    Exp_Control: float = Field(
        default=0.1,
        validation_alias='variation_threshold',
        description='Specifies the maximum tolerable variation of the bunch extensions relative to \
                    the grid cell size within one time step.'
    )

    @computed_field(return_type=bool, repr=True)
    @property
    def L2D_3D(self):
        return False if self.z_trans is None else True

    def to_ini(self) -> str:
        return "&CHARGE" + self._to_ini() + "/"


@ini_exportable
class SimulationOutputSpecification(BaseModel):
    ZSTART: float = Field(
        default=0.0,
        validation_alias='z_start',
        description='Minimal z position for the generation of output.',
        json_schema_extra={'format': 'Unit: [m]'},
    )
    ZSTOP: float = Field(
        default=1.0,
        validation_alias='z_stop',
        description='Longitudinal stop position. Tracking will stop when the bunch center passes z_stop.',
        json_schema_extra={'format': 'Unit: [m]'},
    )
    Zemit: int = Field(
        default=100,
        validation_alias='z_emit',
        description='The interval z_stop - z_start is divided into z_emit sub-intervals. At the end of \
                     each sub-interval statistical bunch parameters such as emittance are saved. It is advised to set \
                     a multiple of z_phase as value.',
        gt=1
    )
    Zphase: int = Field(
        default=1,
        validation_alias='z_phase',
        description='The interval z_stop - z_start is divided into z_emit sub-intervals. At the end of \
                     each sub-interval a complete particle distribution is saved.'
    )
    High_res: bool = Field(
        default=True,
        validation_alias='high_accuracy',
        description='If true, particle distributions are saved with increased accuracy'
    )
    RefS: bool = Field(
        default=True,
        validation_alias='high_accuracy',
        description='If true, ASTRA generates output of the off-axis reference trajectory, energy gain etc. at each \
                     Runge-Kutta time step.'
    )
    EmitS: bool = Field(
        default=True,
        validation_alias='generate_emittance_output',
        description='If true, output of the beam emittance and other statistical beam parameters is generated. The parameters \
                    are calculated and stored at the end of each sub-interval defined by z_emit.'
    )
    Tr_emitS: bool = Field(
        default=True,
        validation_alias='generate_ts_emittance_output',
        description='If true, output of the trace space beam emittance and other statistical beam parameters is \
                    generated. The parameters are calculated and stored at the end of each sub-interval defined by z_emit.'
    )
    PhaseS: bool = Field(
        default=True,
        validation_alias='generate_complete_particle_output',
        description='If true, the complete particle distribution is saved at z_phase different locations.'
    )

    def to_ini(self) -> str:
        return "&OUTPUT" + self._to_ini() + "/"


@ini_exportable
class SimulationRunSpecifications(BaseModel):
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
        default=0.1,
        validation_alias='bunch_charge',
        description='Bunch charge in [nC]. Scaling is active if bunch_charge != 0.',
        json_schema_extra={'format': 'Unit: [nC]'}
    )
    Q_Schottky: float = Field(
        default=0.0,
        validation_alias='bunch_charge',
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


@ini_exportable
class SimulationInput(BaseModel):
    _timestamp: str | None = None

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def run_dir(self):
        return f"{SIMULATION_DATA_PATH}/{self.timestamp}"

    run_specs: SimulationRunSpecifications = Field(
        default=SimulationRunSpecifications(),
        description=''
    )
    output_specs: SimulationOutputSpecification = Field(
        default=SimulationOutputSpecification(),
        description='Specifications about the output files generated by the simulation.'
    )
    cavities: list[Cavity] = Field(
        default=[],
        description='Specifications of cavities existing in the simulation setup. If not specified differently, \
            cavities will be ordered w.r.t. to the z_0 parameter values.',
    )
    solenoids: list[Solenoid] = Field(
        default=[],
        description='Specifications of solenoids existing in the simulation setup. If not specified differently, \
            solenoids will be ordered w.r.t. to the z_0 parameter values.',
    )
    space_charge: SpaceCharge = Field(
        default=SpaceCharge(),
        description=''
    )

    def sort_and_set_ids(self, attribute_key: str) -> None:
        attr = getattr(self, attribute_key)
        if not np.any(list(map(lambda o: o.z_0 is None, attr))):
            setattr(self, attribute_key, sorted(attr, key=lambda element: element.z_0))
        for idx, element in enumerate(getattr(self, attribute_key), start=1):
            element.id = idx

    def model_post_init(self, __context) -> None:
        self.sort_and_set_ids('cavities')
        self.sort_and_set_ids('solenoids')
        self._timestamp = str(datetime.now().timestamp())

    def to_ini(self) -> str:
        has_cavities = str(len(self.cavities) > 0).lower()
        has_solenoids = str(len(self.solenoids) > 0).lower()
        cavity_str = f"&CAVITY\n    LEfield = {has_cavities}\n{''.join([c.to_ini() for c in self.cavities])}/"
        solenoid_str = f"&SOLENOID\n    LBfield = {has_solenoids}\n{''.join([s.to_ini() for s in self.solenoids])}/"
        run_str = self.run_specs.to_ini()
        charge_str = self.space_charge.to_ini()
        output_str = self.output_specs.to_ini()

        return "\n\n".join([run_str, output_str, charge_str, cavity_str, solenoid_str]) + "\n"

    @property
    def input_filename(self) -> str:
        return f"{self.run_dir}/run.in"

    def write_to_disk(self) -> str:
        os.mkdir(self.run_dir)
        ini_string = self.to_ini()
        with open(self.input_filename, "w") as input_file:
            input_file.write(ini_string)
        for o in self.solenoids + self.cavities:
            o.write_to_disk(self.run_dir)

        return ini_string


class XYEmittanceTable(BaseModel):
    z: list[float] = Field(
        description='Longitudinal positions.',
        json_schema_extra={'format': 'Unit: [m]'}
    )
    t: list[float] = Field(
        description='Time points',
        json_schema_extra={'format': 'Unit: [ns]'}
    )
    mean: list[float] = Field(
        description='Average transverse position in x or y direction.',
        json_schema_extra={'format': 'Unit: [mm]'}
    )
    position_rms: list[float] = Field(
        description='RMS deviation in x or y direction.',
        json_schema_extra={'format': 'Unit: [mm]'}
    )
    angle_rms: list[float] = Field(
        description='RMS inclination angle deviation in x or y direction.',
        json_schema_extra={'format': 'Unit: [mrad]'}
    )
    emittance:  list[float] = Field(
        description='Normed emittance in x or y direction.',
        json_schema_extra={'format': 'Unit: [pi*mrad*mm]'}
    )
    correlation: list[float] = Field(
        description='Correlation of position coordinates and momenta in x or y direction.',
        json_schema_extra={'format': 'Unit: [mrad]'}
    )


class ZEmittanceTable(BaseModel):
    z: list[float] = Field(
        description='Longitudinal positions.',
        json_schema_extra={'format': 'Unit: [m]'}
    )
    t: list[float] = Field(
        description='Time points',
        json_schema_extra={'format': 'Unit: [ns]'}
    )
    E_kin: list[float] = Field(
        description='Average transverse position in x or y direction.',
        json_schema_extra={'format': 'Unit: [MeV]'}
    )
    position_rms: list[float] = Field(
        description='RMS deviation in x or y direction.',
        json_schema_extra={'format': 'Unit: [mm]'}
    )
    delta_E_rms: list[float] = Field(
        description='RMS inclination angle deviation in x or y direction.',
        json_schema_extra={'format': 'Unit: [keV]'}
    )
    emittance: list[float] = Field(
        description='Normed emittance in x or y direction.',
        json_schema_extra={'format': 'Unit: [pi*keV*mm]'}
    )
    correlation: list[float] = Field(
        description='Correlation of position coordinates and mean energy in x or y direction.',
        json_schema_extra={'format': 'Unit: [keV]'}
    )


class SimulationOutput(BaseModel):
    timestamp: str
    input_ini: str
    run_output: str
    particles: Optional[list[Particles]] = Field(
        default=[Particles()]
    )
    emittance_x: Optional[XYEmittanceTable] = Field(
        default=None,
    )
    emittance_y: Optional[XYEmittanceTable] = Field(
        default=None,
    )
    emittance_z: Optional[ZEmittanceTable] = Field(
        default=None
    )