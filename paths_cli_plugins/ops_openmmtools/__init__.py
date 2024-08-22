from paths_cli.compiling.plugins import EngineCompilerPlugin
# from paths_cli.compiling.tools import custom_eval_int_strict_pos
from paths_cli.compiling.json_type import json_type_eval
from paths_cli.compiling.core import (
    Builder, Parameter, InstanceCompilerPlugin
)
from paths_cli.compiling.engines import (
    OPENMM_PARAMETERS, load_openmm_xml, _openmm_options
)
from functools import partial

_param_mapping = {param.name: param for param in OPENMM_PARAMETERS}

def unit_eval(string, expected_unit):
    from openmm import unit
    namespace = {
        'np': __import__('numpy'),
        'math': __import__('math'),
        'unit': unit,
    }
    # TODO: when core CLI has protections for eval, add them here
    value = eval(str(string), namespace)
    quantity = eval(f"1.0 * {expected_unit}", namespace)
    # raises an error if this is a bad unit
    _ = value.value_in_unit(quantity.unit)
    return value

def unit_eval_temperature(string):
    from openmm import unit
    val = unit_eval(string, 'unit.kelvin')
    if val.value_in_unit(unit.kelvin) <= 0:
        raise ...  # what kind of error?
    return val


class BuilderWithOpenMMXmlFallback:
    def __init__(self, supported):
        self.supported = supported

    def __call__(self, obj_info):
        if isinstance(obj_info, str):
            return load_openmm_xml(obj_info)

        builder = self.supported[obj_info['type']]
        return builder(obj_info)


class OpenMMToolsIntegratorPlugin(InstanceCompilerPlugin):
    pass


class OpenMMToolsTestSystemPlugin(InstanceCompilerPlugin):
    pass


LANGEVIN_INTEGRATOR_PARAMETERS = [
    Parameter(
        "temperature",
        unit_eval_temperature,
        json_type="string",
        description="unitted quantity for the temperature"
    ),
    Parameter(
        "collision_rate",
        partial(unit_eval, expected_unit='1.0 / unit.picosecond'),
        json_type='string',
        description='unitted quantity for the collision rate',
    ),
    Parameter(
        "timestep",
        partial(unit_eval, expected_unit="unit.femtosecond"),
        json_type="string",
        description="unitted quantity for the timestep",
    ),
]

SUPPORTED_INTEGRATORS = {
    'VVVRIntegrator': OpenMMToolsIntegratorPlugin(
        Builder('openmmtools.integrators.VVVRIntegrator'),
        parameters=LANGEVIN_INTEGRATOR_PARAMETERS,
        name="vvvr",
        description="VVVR integrator",
    ),
    'BAOABIntegrator': OpenMMToolsIntegratorPlugin(
        Builder('openmmtools.integrators.BAOABIntegrator'),
        parameters=LANGEVIN_INTEGRATOR_PARAMETERS,
        name='baoab',
        description="BAOAB integrator",
    ),
}

DW_TESTSYSTEM_PARAMETERS = [
]

SUPPORTED_TESTSYSTEMS = {
    'DoubleWellDimer_WCAFluid': OpenMMToolsTestSystemPlugin(
        Builder('openmmtools.testsystems.DoubleWellDimer_WCAFluid'),
        parameters=[
            Parameter('ndimers', int, json_type="Number",
                      description="Number of double well dimers")
        ] + DW_TESTSYSTEM_PARAMETERS,
        name="dwdimer_wca",
        description="",
    ),
    'DoubleWellChain_WCAFluid': OpenMMToolsTestSystemPlugin(
        Builder('openmmtools.testsystems.DoubleWellChain_WCAFluid'),
        parameters=[
            Parameter("nchains", int, json_type="Number",
                     description="")
        ] + DW_TESTSYSTEM_PARAMETERS,
        name="dwchain_wca",
        description=""
    ),
}


_param_updates = {
    'system': Parameter(
        "system",
        BuilderWithOpenMMXmlFallback(SUPPORTED_TESTSYSTEMS),
        json_type=...,
        description=("XML file for the OpenMM system or description of an "
                     "OpenMMTools TestSystem"),
    ),
    'integrator': Parameter(
        "integrator",
        BuilderWithOpenMMXmlFallback(SUPPORTED_INTEGRATORS),
        json_type=...,
        description=("XML file for the OpenMM integrator or description of "
                     "an OpenMMTools integrator")
    ),
}

# create dict using the updated parameters, list of values is our param list
PARAMETERS = list((_param_mapping | _param_updates).values())

def _openmmtools_remapper(kwargs):
    import openmmtools
    system = kwargs.get('system')
    if isinstance(system, openmmtools.testsystems.TestSystem):
        system = system.system
    kwargs['system'] = system
    return _openmm_options(kwargs)

OPENMMTOOLS_ENGINE = EngineCompilerPlugin(
    builder=Builder(
        "openpathsampling.engines.openmm.Engine",
        remapper=_openmmtools_remapper
    ),
    name='openmmtools',
    parameters=PARAMETERS,
    description=("Use OpenMM for the dynamics; with conveniences for using "
                 "integrators and testsystems from OpenMMTools."),
)
