import os
import json
import numpy as np
from datetime import datetime
from shortuuid import uuid
from typing import Optional
from pydantic import BaseModel, Field
from astra_web.decorators.decorators import ini_exportable
from astra_web.utils import SIMULATION_DATA_PATH
from astra_web.generator.schemas.particles import Particles
from .run import SimulationRunSpecifications
from .modules import Solenoid, Cavity
from .space_charge import SpaceCharge
from .tables import XYEmittanceTable, ZEmittanceTable

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
        validation_alias='emittance_checkpoint_num',
        description='The interval z_stop - z_start is divided into z_emit sub-intervals. At the end of \
                     each sub-interval statistical bunch parameters such as emittance are saved. It is advised to set \
                     a multiple of z_phase as value.',
        gt=1
    )
    Zphase: int = Field(
        default=1,
        validation_alias='distribution_checkpoint_num',
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
class SimulationInput(BaseModel):
    _sim_id: str | None = None

    @property
    def sim_id(self):
        return self._sim_id

    @property
    def run_dir(self):
        dir_name = self.sim_id if self.run_specs.run_dir is None else self.run_specs.run_dir
        return f"{SIMULATION_DATA_PATH}/{dir_name}"

    run_specs: SimulationRunSpecifications = Field(
        default=SimulationRunSpecifications(),
        description='Specifications of operative run parameters such as thread numbers, run directories and more.'
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
        self._sim_id = f"{datetime.now().strftime('%Y-%m-%d')}-{uuid()[:8]}"
        os.mkdir(self.run_dir)
        self.sort_and_set_ids('cavities')
        self.sort_and_set_ids('solenoids')
        with open(f"{self.run_dir}/input.json", "w") as f:
            data = {
                "solenoid_strength": self.solenoids[0].MaxB,
                "spot_size": self.run_specs.XYrms,
                "emission_time": self.run_specs.Trms,
                "gun_phase": self.cavities[0].Phi,
                "gun_gradient": self.cavities[0].MaxE,
                "input_distribution": self.run_specs.particle_file_name,
            }
            str_ = json.dumps(data,
                              indent=4, sort_keys=True,
                              separators=(',', ': '),
                              ensure_ascii=False)
            f.write(str_)

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
        if not os.path.exists(self.run_dir): os.mkdir(self.run_dir)
        ini_string = self.to_ini()
        with open(self.input_filename, "w") as input_file:
            input_file.write(ini_string)
        for o in self.solenoids + self.cavities:
            o.write_to_disk(self.run_dir)

        return ini_string


class SimulationOutput(BaseModel):
    sim_id: str
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


class StatisticsInput(BaseModel):
    sim_id: str
    z_pos: int = Field(
        default=-1,
        description='Longitudinal position at which statistics will be calculated.'
    )
    n_slices: int = Field(
        default=20,
        description='Number of slices to be used for slice emittance calculation.'
    )


class StatisticsOutput(BaseModel):
    sim_id: str
    particle_count: int = Field(
        description='Total number of particles.'
    )
    active_particle_count: int = Field(
        description='Number of active particles.'
    )
    z_pos: float = Field(
        default=-1,
        description='Longitudinal position at which statistics were calculated.'
    )
    inputs: dict = Field(
        default={},
        description='Dictionary holding initial inputs to the simulation.'
    )
    slice_emittances: list[tuple[float, float]] = Field(
        default=[],
        description='Slice emittances for a bunch at a certain longitudinal position.'
    )