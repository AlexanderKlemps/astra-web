from aenum import MultiValueEnum


class Distribution(str, MultiValueEnum):
    gauss = "gaussian", "gauss", "g"
    uniform = "uniform", "u"
    plateau = "plateau", "p", "flattop"
    inverted = "inverted", "i"
    r = "radial_uniform", "r"
    isotropic = "isotropic"
    FD_300 = "fd_300"


class ParticleType(str, MultiValueEnum):
    electrons = 'electrons', "el", "e"
    positrons = 'positrons', 'po'
    protons = 'protons', 'pr'
    hydrogen = 'hydrogen', 'hy'


