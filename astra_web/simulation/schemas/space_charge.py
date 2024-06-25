from pydantic import BaseModel, Field, ConfigDict, computed_field, model_serializer
from astra_web.decorators.decorators import ini_exportable

@ini_exportable
class SpaceCharge(BaseModel):
    LSPCH: bool = Field(
        default=False,
        validation_alias='use_space_charge',
        description='Toggle whether to calculate space charge fields or not.'
    )
    LSPCH3D: bool = Field(
        default=False,
        validation_alias='use_3d_space_charge',
        description='Toggle whether to calculate 3D space charge fields with an FFT algorithm or not.'
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
    Nlong_in: int = Field(
        default=10,
        validation_alias='longitudinal_grid_size',
        description='Maximum number of grid cells in longitudinal direction within the bunch \
                     length. During the emission process the number is reduced, according to the \
                     specification of the minimum cell length min_grid. Only for cylindrical grid \
                     algorithm.'
    )
    N_min: int = Field(
        default=10,
        validation_alias='emitted_particle_num_per_step',
        description='Average number of particles to be emitted in one step during the emission from \
                     a cathode. N_min is needed to set H_min automatically during emission. Only \
                     for cylindrical grid algorithm.'
    )

    @computed_field(return_type=bool, repr=True)
    @property
    def L2D_3D(self):
        if self.z_trans is None:
            return False
        else:
            return True

    def to_ini(self) -> str:
        return "&CHARGE" + self._to_ini() + "/"