from .tables import ApertureTable, FieldTable
from typing import Any, Literal, Self
from pydantic import (BaseModel, Field, ConfigDict, FiniteFloat, computed_field,
                      field_validator, model_serializer, model_validator)
from astra_web.decorators.decorators import ini_exportable


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
        prefix = "TWS_" if self.field_table is not None and self.field_table.traveling_wave is not None else ""
        return f"{prefix}C{self.id}_E.dat"

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
        title='Peak on-axis electric field [MV/m]',
        description='Peak on-axis longitudinal electric-field amplitude in MV/m (ASTRA MaxE).',
        json_schema_extra={'format': 'Unit: [MV/m]'}
    )

    C_numb: int | None = Field(
        default=None,
        gt=0,
        validation_alias='cell_count',
        description='Number of traveling-wave cells, excluding input and output coupler cells.'
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

    @model_validator(mode='after')
    def validate_field_table(self):
        if self.field_table is not None and self.field_table.traveling_wave is not None:
            raise ValueError('Traveling-wave field tables are supported for cavities, not solenoids')
        return self

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
class Quadrupole(Module):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: int = Field(
        default=None,
        exclude=True,
        description="The ID of the quadrupole."
    )
    Q_length: float = Field(
        default=None,
        validation_alias='q_len',
        description='Effective Length of the Quadrupole.',
        json_schema_extra={'format': 'Unit: [m]'},
    )
    Q_K: float = Field(
        default=10,
        validation_alias='q_focus',
        description='Focusing strength of the quadrupole.',
        json_schema_extra = {'format': 'Unit: [m^-2]'}
    )
    Q_Bore: float = Field(
        default=0.035,
        validation_alias='bore_radius',
        description='Taper parameter for quadrupole field edge.',
        json_schema_extra={'format': 'Unit: [m]'}
    )
    Q_pos: float = Field(
        default=None,
        validation_alias='z_0',
        description='Longitudinal quadrupole position.',
        json_schema_extra={'format': 'Unit: [m]'}
    )

    @property
    def z_0(self):
        return self.Q_pos


class Aperture(Module):
    """An aperture contour or one of ASTRA's built-in aperture geometries."""

    model_config = ConfigDict(extra='forbid')

    id: int | None = Field(default=None, exclude=True)
    aperture_type: Literal['table', 'RAD', 'Cir', 'Scr_X', 'Scr_Y', 'Col_X', 'Col_Y'] = Field(
        default='table', validation_alias='type', exclude=True,
        description='Use table for a contour, or an ASTRA keyword for a built-in geometry.'
    )
    aperture_table: ApertureTable | None = Field(default=None, exclude=True)
    Ap_Z1: FiniteFloat | None = Field(
        default=None, validation_alias='z_start', description='Local start position in metres; keyword geometries only.'
    )
    Ap_Z2: FiniteFloat | None = Field(
        default=None, validation_alias='z_end', description='Local end position in metres; keyword geometries only.'
    )
    Ap_R: FiniteFloat | None = Field(
        default=None, validation_alias='radius',
        description='Millimetres: signed radius for RAD (negative means plug), signed scraper distance, or collimator half gap.'
    )
    grid_radii: list[FiniteFloat] | None = Field(
        default=None, exclude=True, min_length=2, max_length=40,
        description='Cir only: alternating inner and outer radii of up to 20 grid rings, in millimetres.'
    )
    A_pos: FiniteFloat = Field(
        default=0.0, validation_alias='z_offset', description='Longitudinal shift in metres, added to local geometry positions.'
    )
    A_xoff: FiniteFloat = Field(default=0.0, validation_alias='x_offset', description='Horizontal offset in metres.')
    A_yoff: FiniteFloat = Field(default=0.0, validation_alias='y_offset', description='Vertical offset in metres.')
    A_xrot: FiniteFloat = Field(default=0.0, validation_alias='xz_rotation', description='Rotation in the x-z plane, in radians.')
    A_yrot: FiniteFloat = Field(default=0.0, validation_alias='yz_rotation', description='Rotation in the y-z plane, in radians.')
    A_zrot: FiniteFloat = Field(default=0.0, validation_alias='xy_rotation', description='Rotation in the x-y plane, in radians.')

    @field_validator('aperture_type', mode='before')
    @classmethod
    def normalize_type(cls, value):
        if isinstance(value, str):
            keywords = {name.lower(): name for name in ('table', 'RAD', 'Cir', 'Scr_X', 'Scr_Y', 'Col_X', 'Col_Y')}
            return keywords.get(value.lower(), value)
        return value

    @model_validator(mode='after')
    def validate_geometry(self) -> Self:
        if self.aperture_type == 'table':
            if self.aperture_table is None:
                raise ValueError('A table aperture requires aperture_table')
            if any(value is not None for value in (self.Ap_Z1, self.Ap_Z2, self.Ap_R, self.grid_radii)):
                raise ValueError('Table apertures cannot also specify z_start, z_end, radius, or grid_radii')
        else:
            if self.aperture_table is not None:
                raise ValueError('Keyword apertures cannot also specify aperture_table')
            if self.Ap_Z1 is None or self.Ap_Z2 is None or self.Ap_Z1 >= self.Ap_Z2:
                raise ValueError('Keyword apertures require z_start < z_end')
            if self.aperture_type == 'Cir':
                if self.Ap_R is not None:
                    raise ValueError('Cir apertures use grid_radii, not radius')
                radii = self.grid_radii
                if radii is None or len(radii) % 2:
                    raise ValueError('Cir requires pairs of inner and outer grid_radii')
                if any(radius < 0 for radius in radii):
                    raise ValueError('Grid radii must be nonnegative')
                if any(outer <= inner for inner, outer in zip(radii[::2], radii[1::2])):
                    raise ValueError('Each grid ring requires inner radius < outer radius')
                if any(right < left for left, right in zip(radii, radii[1:])):
                    raise ValueError('Grid rings must be ordered and cannot overlap')
            else:
                if self.grid_radii is not None:
                    raise ValueError('Only Cir apertures accept grid_radii')
                if self.Ap_R is None:
                    raise ValueError('This aperture type requires radius')
                if self.aperture_type in ('Col_X', 'Col_Y') and self.Ap_R <= 0:
                    raise ValueError('Collimator radius (half gap) must be positive')
        return self

    @computed_field(return_type=str)
    @property
    def File_Aperture(self) -> str:
        return f'A{self.id}.dat' if self.aperture_type == 'table' else self.aperture_type

    @property
    def z_0(self) -> float:
        local_start = self.aperture_table.z[0] if self.aperture_table is not None else self.Ap_Z1
        return self.A_pos + local_start

    def ser_model(self) -> dict[str, Any]:
        out_dict = super().ser_model()
        out_dict[f'File_Aperture({self.id})'] = self.File_Aperture
        if self.grid_radii is not None:
            for index, radius in enumerate(self.grid_radii, start=1):
                out_dict[f'Ap_GR({self.id},{index})'] = radius
        return out_dict

    def to_ini(self) -> str:
        # The shared JSON-based formatter removes commas, including Ap_GR(i,j).
        lines = []
        for key, value in self.ser_model().items():
            encoded = f"'{value}'" if isinstance(value, str) else str(value)
            lines.append(f'    {key} = {encoded}\n')
        return ''.join(lines)

    def write_to_disk(self, path) -> None:
        if self.aperture_table is not None:
            self.aperture_table.to_csv(f'{path}/{self.File_Aperture}')
