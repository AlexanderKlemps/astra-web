from .tables import FieldTable
from typing import Any
from pydantic import BaseModel, Field, ConfigDict, computed_field, model_serializer
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
    Q_bore: float = Field(
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
