import pybamm
import pytest

from backend.parameters.ocp_tables import (
    EAFIT_OCP_TABLES,
    ocp_interpolant,
    validate_ocp_tables,
)
from backend.simulation.runner import prepare

EXPERIMENT = {
    "type": "discharge",
    "current_mode": "c_rate",
    "c_rate": 1,
    "duration_s": 30,
    "temperature_K": 298.15,
}


def _value(fn, sto):
    return float(fn(pybamm.Scalar(sto)).evaluate().item())


def test_negative_interpolant_endpoints():
    fn = ocp_interpolant(EAFIT_OCP_TABLES["negative"])
    assert _value(fn, 0.0) == pytest.approx(1.30)
    assert _value(fn, 1.0) == pytest.approx(0.03)


def test_positive_interpolant_endpoints():
    fn = ocp_interpolant(EAFIT_OCP_TABLES["positive"])
    assert _value(fn, 0.17) == pytest.approx(3.95)
    assert _value(fn, 1.0) == pytest.approx(2.30)


def test_prepare_with_tables_sets_both_ocp_callables():
    prepared, errors, _warnings = prepare(
        "sodium_ion", {}, EXPERIMENT, ocp_tables=EAFIT_OCP_TABLES
    )
    assert errors == []
    assert prepared is not None
    parameter_values, _spec, _merged = prepared
    assert callable(parameter_values["Negative electrode OCP [V]"])
    assert callable(parameter_values["Positive electrode OCP [V]"])


def test_prepare_without_tables_keeps_chayambuka_functions():
    prepared, errors, _warnings = prepare("sodium_ion", {}, EXPERIMENT)
    assert errors == []
    parameter_values, _spec, _merged = prepared
    original = pybamm.ParameterValues("Chayambuka2022")
    assert parameter_values["Negative electrode OCP [V]"] is original["Negative electrode OCP [V]"]
    assert parameter_values["Positive electrode OCP [V]"] is original["Positive electrode OCP [V]"]


def test_single_point_table_is_an_error_without_parameter_set():
    tables = {"negative": [{"sto": 0.0, "V": 1.3}]}
    assert validate_ocp_tables(tables)
    prepared, errors, _warnings = prepare(
        "sodium_ion", {}, EXPERIMENT, ocp_tables=tables
    )
    assert prepared is None
    assert errors


def test_non_increasing_sto_is_an_error_without_parameter_set():
    tables = {
        "negative": [
            {"sto": 0.0, "V": 1.3},
            {"sto": 0.0, "V": 1.0},
        ]
    }
    assert validate_ocp_tables(tables)
    prepared, errors, _warnings = prepare(
        "sodium_ion", {}, EXPERIMENT, ocp_tables=tables
    )
    assert prepared is None
    assert errors


def test_empty_electrode_does_not_replace_ocp():
    prepared, errors, _warnings = prepare(
        "sodium_ion", {}, EXPERIMENT, ocp_tables={"negative": []}
    )
    assert errors == []
    parameter_values, _spec, _merged = prepared
    original = pybamm.ParameterValues("Chayambuka2022")
    assert parameter_values["Negative electrode OCP [V]"] is original["Negative electrode OCP [V]"]
