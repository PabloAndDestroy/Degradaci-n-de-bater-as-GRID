import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.parameters.catalogue import CATEGORIES, list_parameters
from backend.simulation.runner import simulate


def _discharge(**overrides):
    return simulate(
        "sodium_ion",
        overrides,
        {
            "type": "discharge",
            "current_mode": "c_rate",
            "c_rate": 1,
            "duration_s": 30,
            "temperature_K": 298.15,
        },
        variables=[
            "Voltage [V]",
            "Current [A]",
            "Discharge capacity [A.h]",
            "Electrolyte concentration (x-average) [mol.m-3]",
            "Negative particle concentration (r-average, x-average) [mol.m-3]",
        ],
    )


def test_parameter_catalogue_matches_pybamm():
    catalogue = list_parameters("sodium_ion")
    names = [row["name"] for row in catalogue["parameters"]]
    assert "citations" not in names
    assert set(names) == set(CATEGORIES)
    thickness = next(
        row for row in catalogue["parameters"] if row["name"] == "Negative electrode thickness [m]"
    )
    assert thickness["original"] == pytest.approx(64e-6)
    assert thickness["unit"] == "m"
    assert thickness["editable"] is True
    ocp = next(row for row in catalogue["parameters"] if row["name"] == "Negative electrode OCP [V]")
    assert ocp["type"] == "function"
    assert ocp["editable"] is False
    assert catalogue["citations"] == ["Chayambuka2022"]


def test_short_discharge_has_voltage_and_time():
    result = _discharge()
    time = np.asarray(result["series"]["Time [s]"])
    voltage = np.asarray(result["series"]["Voltage [V]"])
    current = np.asarray(result["series"]["Current [A]"])
    capacity = np.asarray(result["series"]["Discharge capacity [A.h]"])
    assert result["termination"]
    assert time.shape == voltage.shape == current.shape == capacity.shape
    assert time.size > 2
    assert np.all(np.diff(time) >= 0)
    assert time[0] == pytest.approx(0)
    assert time[-1] == pytest.approx(30)
    assert voltage[0] == pytest.approx(3.8213, abs=1e-3)
    assert voltage[-1] < voltage[0]
    assert current[-1] == pytest.approx(3e-3)
    assert capacity[-1] == pytest.approx(current[-1] * time[-1] / 3600)


def test_initial_fields_match_the_parameter_set():
    result = _discharge()
    electrolyte = result["series"]["Electrolyte concentration (x-average) [mol.m-3]"]
    particles = result["series"]["Negative particle concentration (r-average, x-average) [mol.m-3]"]
    assert electrolyte[0] == pytest.approx(1000, abs=1e-6)
    assert particles[0] == pytest.approx(13520, rel=1e-3)


def test_thickness_changes_voltage_and_contact_resistance_does_not():
    base = _discharge()
    thicker = _discharge(**{"Positive electrode thickness [m]": 100e-6})
    contact = _discharge(**{"Contact resistance [Ohm]": 50})
    assert thicker["series"]["Voltage [V]"][-1] != pytest.approx(
        base["series"]["Voltage [V]"][-1]
    )
    assert contact["series"]["Voltage [V]"] == pytest.approx(base["series"]["Voltage [V]"])


def test_rejects_negative_thickness_and_function_override():
    client = TestClient(app)
    response = client.post(
        "/api/simulate",
        json={
            "model": "sodium_ion",
            "parameters": {"Negative electrode thickness [m]": -1},
            "experiment": {
                "type": "discharge",
                "current_mode": "current",
                "current_A": 0.003,
                "duration_s": 10,
                "temperature_K": 298.15,
            },
        },
    )
    assert response.status_code == 422
    payload = response.json()
    assert "Negative electrode thickness" in " ".join(payload["details"])

    response = client.post(
        "/api/parameters/validate",
        json={
            "model": "sodium_ion",
            "parameters": {"Negative electrode OCP [V]": 3.5},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert any("función" in item for item in body["errors"])


def test_custom_nominal_capacity_allows_current_within_50c_limit():
    client = TestClient(app)
    response = client.post(
        "/api/parameters/validate",
        json={
            "model": "sodium_ion",
            "parameters": {"Nominal cell capacity [A.h]": 0.12},
            "experiment": {
                "type": "discharge",
                "current_mode": "current",
                "current_A": 6,
                "duration_s": 10,
                "temperature_K": 298.15,
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_charge_at_one_c_reports_initial_voltage_cutoff():
    client = TestClient(app)
    response = client.post(
        "/api/simulate",
        json={
            "model": "sodium_ion",
            "parameters": {},
            "experiment": {
                "type": "charge",
                "current_mode": "c_rate",
                "c_rate": 1,
                "duration_s": 30,
                "temperature_K": 298.15,
            },
            "variables": ["Voltage [V]"],
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert "No se puede iniciar la carga" in payload["error"]
    assert any("Reduzca el C-rate" in item for item in payload["details"])


def test_api_parameters_and_simulation():
    client = TestClient(app)
    models = client.get("/api/models")
    assert models.status_code == 200
    assert any(item["id"] == "sodium_ion" and item["implemented"] for item in models.json()["models"])

    variables = client.get("/api/models/sodium_ion/variables")
    assert variables.status_code == 200
    names = {item["name"] for item in variables.json()["variables"]}
    assert "Voltage [V]" in names
    assert "Temperature [K]" not in names

    saved = client.post(
        "/api/configurations",
        json={
            "name": "descarga 1C",
            "model": "sodium_ion",
            "parameters": {},
            "experiment": {
                "type": "discharge",
                "current_mode": "c_rate",
                "c_rate": 1,
                "duration_s": 20,
                "temperature_K": 298.15,
            },
        },
    )
    assert saved.status_code == 200

    compared = client.post(
        "/api/simulate/compare",
        json={
            "cases": [
                {
                    "label": "A",
                    "model": "sodium_ion",
                    "parameters": {},
                    "experiment": {
                        "type": "discharge",
                        "current_mode": "c_rate",
                        "c_rate": 1,
                        "duration_s": 15,
                        "temperature_K": 298.15,
                    },
                    "variables": ["Voltage [V]"],
                },
                {
                    "label": "B",
                    "model": "sodium_ion",
                    "parameters": {"Positive electrode thickness [m]": 90e-6},
                    "experiment": {
                        "type": "discharge",
                        "current_mode": "c_rate",
                        "c_rate": 1,
                        "duration_s": 15,
                        "temperature_K": 298.15,
                    },
                    "variables": ["Voltage [V]"],
                },
            ]
        },
    )
    assert compared.status_code == 200, compared.text
    cases = compared.json()["cases"]
    assert len(cases) == 2
    assert len(cases[0]["series"]["Time [s]"]) == len(cases[0]["series"]["Voltage [V]"])
    assert cases[0]["series"]["Voltage [V]"][-1] != pytest.approx(cases[1]["series"]["Voltage [V]"][-1])
