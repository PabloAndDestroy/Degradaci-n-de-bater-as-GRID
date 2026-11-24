"""Capa HTTP para las tablas OCP opcionales del agregado EAFIT."""

from fastapi.testclient import TestClient

import backend.simulation.runner as runner
import pybamm
from backend.main import app
from backend.parameters.ocp_tables import EAFIT_OCP_TABLES

client = TestClient(app)

EXPERIMENT = {
    "type": "discharge",
    "current_mode": "c_rate",
    "c_rate": 1,
    "duration_s": 30,
    "temperature_K": 298.15,
}

SINGLE_POINT = {"negative": [{"sto": 0.0, "V": 1.30}]}
NON_INCREASING = {
    "negative": [
        {"sto": 0.0, "V": 1.30},
        {"sto": 0.0, "V": 1.00},
    ]
}


def _validate(parameters=None, ocp_tables=None):
    payload = {"model": "sodium_ion", "parameters": parameters or {}}
    if ocp_tables is not None:
        payload["ocp_tables"] = ocp_tables
    return client.post("/api/parameters/validate", json=payload)


def _simulate(ocp_tables=None, parameters=None):
    return client.post(
        "/api/simulate",
        json={
            "model": "sodium_ion",
            "parameters": parameters or {},
            "experiment": EXPERIMENT,
            "variables": ["Voltage [V]"],
            "ocp_tables": ocp_tables,
        },
    )


def test_validate_rejects_single_point_table():
    # El endpoint de validate ya responde 200 con valid=false; no exige 422.
    response = _validate(ocp_tables=SINGLE_POINT)
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert any("al menos 2 puntos" in item for item in body["errors"])


def test_validate_rejects_non_increasing_sto():
    response = _validate(ocp_tables=NON_INCREASING)
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert any("creciente" in item for item in body["errors"])


def test_validate_accepts_canonical_tables():
    response = _validate(ocp_tables=EAFIT_OCP_TABLES)
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_validate_accumulates_override_and_ocp_errors():
    response = _validate(
        parameters={"Negative electrode OCP [V]": 3.5},
        ocp_tables=SINGLE_POINT,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    text = " ".join(body["errors"])
    assert "función" in text
    assert "ocp_tables" in text


def test_simulate_refuses_bad_tables_without_solving(monkeypatch):
    def forbidden_solve(*_args, **_kwargs):
        raise AssertionError("El DFN no debía resolverse con tablas inválidas.")

    monkeypatch.setattr(pybamm.Simulation, "solve", forbidden_solve)
    response = _simulate(ocp_tables=SINGLE_POINT)
    assert response.status_code == 422
    payload = response.json()
    assert any("ocp_tables" in item for item in payload["details"])
    assert "series" not in payload


def test_simulate_refuses_non_increasing_sto():
    response = _simulate(ocp_tables=NON_INCREASING)
    assert response.status_code == 422
    payload = response.json()
    assert any("creciente" in item for item in payload["details"])
    assert "series" not in payload


def test_simulate_forwards_ocp_tables_to_runner(monkeypatch):
    captured = {}

    def fake_prepare(_model_id, _overrides, _experiment, ocp_tables=None):
        captured["ocp_tables"] = ocp_tables
        return None, ["stop"], []

    monkeypatch.setattr(runner, "prepare", fake_prepare)
    tables = {"negative": EAFIT_OCP_TABLES["negative"]}
    response = _simulate(ocp_tables=tables)
    assert response.status_code == 422
    assert captured["ocp_tables"] == tables


def test_numeric_ocp_override_is_still_rejected():
    parameters = {"Negative electrode OCP [V]": 3.5}

    validated = _validate(parameters=parameters)
    assert validated.status_code == 200
    assert validated.json()["valid"] is False
    assert any("función" in item for item in validated.json()["errors"])

    simulated = _simulate(parameters=parameters)
    assert simulated.status_code == 422
    assert any("función" in item for item in simulated.json()["details"])
