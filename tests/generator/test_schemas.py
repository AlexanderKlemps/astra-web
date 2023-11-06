import pytest
from astra_generator.generator.schemas import Input, Particle
from astra_generator.generator.generator import transform_line


class TestSchemas:
    def test_one(self):
        test_input = Input(Q_total=1E0)
        print(test_input)
        assert isinstance(test_input, Input)

    def test_two(self):
        example_line = "  0.0000E+00  0.0000E+00  0.0000E+00  0.0000E+00  0.0000E+00  2.4585E+06  0.0000E+00 -1.0000E-04   1   5\n"
        transformed_object = transform_line(example_line)
        assert isinstance(transformed_object, Particle)
        assert list(transformed_object.dict().values()) == [0.0, 0.0, 0.0, 0.0, 0.0, 2.4585E+06, 0.0, -0.0001, 1, 5]
