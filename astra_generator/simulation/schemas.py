from pydantic import BaseModel, Field, ConfigDict, computed_field, model_serializer, AliasGenerator
from datetime import datetime
from typing import Any
from astra_generator.decorators.decorators import ini_exportable
import re


class FieldTable(BaseModel):
    z: list[float]
    v: list[float]


class Module(BaseModel):
    @model_serializer
    def ser_model(self) -> dict[str, Any]:
        out_dict = dict()
        for key, val in self:
            if not self.model_fields[key].exclude == True:
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
        description="Table containing lists of longitudinal positions z in [m] and corresponding \
                    field amplitudes v in free units.")

    @computed_field(return_type=str)
    @property
    def File_Efield(self) -> str:
        return f"cavity_{self.id}_E_field.dat"

    Nue: float = Field(
        default=1.3E0,
        validation_alias='frequency',
        description='Frequency of the RF field in [GHz].'
    )
    C_pos: float = Field(
        default=0.0E0,
        validation_alias='z_0',
        description='Leftmost longitudinal cavity position in [m].'
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
        description='Initial phase of the RF field in [deg].'
    )
    MaxE: float = Field(
        default=130.0E0,
        validation_alias='max_field_strength',
        description='Maximum on-axis longitudinal amplitude of the RF field in [MV/m] or [T].'
    )

    #def to_ini(self) -> str:
    #    ini_str = self._to_ini()
    #    re.sub(r'^([^.]*\.[^.]*)\.', r'\1s', ini_str)

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

    _timestamp: str | None = str(datetime.now()).replace(" ", "_")
    id: int = Field(
        default=None,
        exclude=True,
        description="The ID of the solenoid."
    )
    field_table: FieldTable = Field(
        default=None,
        exclude=True,
        description="Table containing lists of longitudinal positions z in [m] and corresponding \
                    field amplitudes v in free units."
    )

    @computed_field(return_type=str)
    @property
    def File_Bfield(self) -> str:
        return f"solenoid_{self.id}_B_field.dat"

    S_pos: float = Field(
        default=0.0E0,
        validation_alias='z_0',
        description='Leftmost longitudinal solenoid position in [m].'
    )
    S_smooth: int = Field(
        default=10,
        validation_alias='smoothing_iterations',
        description='Number of iterations for smoothing of transverse field components.'
    )
    MaxB: float = Field(
        default=130.0E0,
        validation_alias='max_field_strength',
        description='Maximum on-axis longitudinal amplitude of the magnetic field in [T].'
    )

    @property
    def z_0(self):
        return self.S_pos

    def ser_model(self) -> dict[str, Any]:
        out_dict = super().ser_model()
        out_dict[f'File_Bfield({self.id})'] = self.File_Bfield

        return out_dict


@ini_exportable
class SpaceCharge(BaseModel):
    LSPCH: bool = Field(
        default=False,
        validation_alias='use_space_charge',
        description='Toggle whether to calculate space charge fields.'
    )
    z_trans: float = Field(
        default=None,
        description='Longitudinal position in [m] for automatic transition of 2D to 3D space charge\
                    calculation.'
    )
    Lmirror: float = Field(
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
    Exp_control: float = Field(
        default=0.1,
        validation_alias='variation_threshold',
        description='Specifies the maximum tolerable variation of the bunch extensions relative to \
                    the grid cell size within one time step.'
    )

    @computed_field(return_type=bool)
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
        description='Minimal z position for the generation of output in [m].'
    )
    ZSTOP: float = Field(
        default=4.5,
        validation_alias='z_start',
        description='Longitudinal stop position in [m]. Tracking will stop when the bunch center passes z_stop.'
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
        validation_alias='generate_emittance_output',
        description='If true, output of the trace space beam emittance and other statistical beam parameters is \
                    generated. The parameters are calculated and stored at the end of each sub-interval defined by z_emit.'
    )
    PhaseS: bool = Field(
        default=True,
        validation_alias='high_accuracy',
        description='If true, the complete particle distribution is saved at z_phase different locations.'
    )

    def to_ini(self) -> str:
        return "&OUTPUT" + self._to_ini() + "/"


@ini_exportable
class SimulationRunSpecifications(BaseModel):
    Version: int = Field(
        default=3
    )
    Head: str = Field(
        default=f"Simulation run at time {datetime.today().strftime('%H:%M:%S date %Y-%m-%d')}",
        validation_alias='run_name',
        description='Run name for protocol.'
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
        return file_name

    Qbunch: float = Field(
        default=0.1,
        validation_alias='bunch_charge',
        description='Bunch charge in [nC]. Scaling is active if bunch_charge != 0.'
    )
    Q_Schottky: float = Field(
        default=0.0,
        validation_alias='bunch_charge',
        description='Linear variation of the bunch charge in [nC*m/MV] with the field on the cathode. Scaling is \
                     active if Q_Schottky != 0.'
    )
    XYrms: float = Field(
        default=-1.0,
        validation_alias='rms_laser_spot_size',
        description='Horizontal and vertical rms beam size in [mm]. Scaling is active if rms_laser_spot_size > 0.0.'
    )
    Trms: float = Field(
        default=-1.0,
        validation_alias='emission_time',
        description='Emission time of the bunch. Scaling is active if emission_time > 0.0.'
    )
    H_min: float = Field(
        default=0.0,
        validation_alias='start_time',
        description='Minimum time step for the Runge-Kutta integration in [ns] and min. time step for the \
                     space charge calculation.'
    )
    H_max: float = Field(
        default=0.001,
        validation_alias='end_time',
        description='Maximum time step for the Runge-Kutta integration in [ns].'
    )
    Max_step: int = Field(
        default=100000,
        validation_alias='max_iteration',
        description='Safety termination: after Max_step Runge_Kutta steps the run is terminated.'
    )
    Z_Cathode: float = Field(
        default=0.0,
        validation_alias='z_cathode',
        description='Position of the cathode for the calculation of the mirror charge.'
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
    run_specs: SimulationRunSpecifications = Field(
        default=SimulationRunSpecifications(),
        description=''
    )
    output_specs: SimulationOutputSpecification = Field(
        default=SimulationOutputSpecification(),
        description=''
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
        default=SpaceCharge()
    )

    def sort_and_set_ids(self, attribute_key: str) -> None:
        attr = getattr(self, attribute_key)
        setattr(self, attribute_key, sorted(attr, key=lambda element: element.z_0))
        for idx, element in enumerate(getattr(self, attribute_key), start=1):
            element.id = idx

    def model_post_init(self, __context) -> None:
        self.sort_and_set_ids('cavities')
        self.sort_and_set_ids('solenoids')

    def to_ini(self) -> str:
        has_cavities = str(len(self.cavities) > 0).lower()
        has_solenoids = str(len(self.solenoids) > 0).lower()
        cavity_str = f"&CAVITY\n    LEfield = {has_cavities}\n{''.join([c.to_ini() for c in self.cavities])}/"
        solenoid_str = f"&SOLENOID\n    LBfield = {has_solenoids}\n{''.join([s.to_ini() for s in self.solenoids])}/"
        run_str = self.run_specs.to_ini()
        charge_str = self.space_charge.to_ini()
        output_str = self.output_specs.to_ini()
        ini_output = "\n\n".join([run_str, output_str, charge_str, cavity_str, solenoid_str])

        return ini_output

        #return re.sub(r"[\]\[\{\},]|(=\s\[)\s+|\s+\}(?=,)|\s+\](?=,)", "", self._to_ini(indent=2))
