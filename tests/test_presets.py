from fastapi.testclient import TestClient

from backend.main import app
from backend.parameters.presets import PRESETS
from backend.parameters.ocp_tables import EAFIT_OCP_TABLES


def _presets():
    client = TestClient(app)
    response = client.get("/api/models/sodium_ion/presets")
    assert response.status_code == 200
    return response.json()["presets"]


def test_presets_endpoint_lists_chayambuka_and_eafit():
    presets = _presets()
    ids = [preset["id"] for preset in presets]
    assert "chayambuka" in ids
    assert "eafit" in ids


def test_chayambuka_has_empty_overrides():
    chayambuka = next(preset for preset in _presets() if preset["id"] == "chayambuka")
    assert chayambuka["overrides"] == {}


def test_eafit_has_expected_values():
    eafit = next(preset for preset in _presets() if preset["id"] == "eafit")
    overrides = eafit["overrides"]
    experiment = eafit["experiment"]
    assert overrides["Nominal cell capacity [A.h]"] == 75
    assert overrides["Lower voltage cut-off [V]"] == 1.5
    assert overrides["Upper voltage cut-off [V]"] == 3.9
    assert experiment["current_A"] == 24.75
    assert experiment["current_mode"] == "current"
    assert experiment["temperature_K"] == 298.15


def test_eafit_does_not_include_geometry_or_functions():
    eafit = next(preset for preset in _presets() if preset["id"] == "eafit")
    keys = list(eafit["overrides"]) + list(eafit.get("experiment") or {})
    forbidden = (
        "thickness",
        "height",
        "width",
        "Separator porosity",
        "OCP",
        "diffusivity",
        "exchange-current",
        "Current function",
        "Initial temperature",
    )
    for key in keys:
        for fragment in forbidden:
            assert fragment not in key, f"{fragment!r} aparece en {key!r}"


def test_eafit_includes_thermal_and_electrical_overrides():
    eafit = next(preset for preset in _presets() if preset["id"] == "eafit")
    overrides = eafit["overrides"]
    assert overrides["Contact resistance [Ohm]"] == 0
    assert overrides["Reference temperature [K]"] == 298.15
    assert overrides["Ambient temperature [K]"] == 298.15
    assert overrides["Number of electrodes connected in parallel to make a cell"] == 1
    assert overrides["Number of cells connected in series to make a battery"] == 1


def test_eafit_exposes_ocp_table_endpoints():
    eafit = next(preset for preset in _presets() if preset["id"] == "eafit")
    tables = eafit["ocp_tables"]
    assert tables["negative"][0] == {"sto": 0.0, "V": 1.30}
    assert tables["negative"][-1] == {"sto": 1.0, "V": 0.03}
    assert tables["positive"][0] == {"sto": 0.17, "V": 3.95}
    assert tables["positive"][-1] == {"sto": 1.0, "V": 2.30}


def test_chayambuka_has_no_ocp_tables():
    chayambuka = next(preset for preset in _presets() if preset["id"] == "chayambuka")
    assert chayambuka.get("ocp_tables") is None


def test_ocp_tables_are_not_numeric_overrides():
    eafit = next(preset for preset in _presets() if preset["id"] == "eafit")
    assert "ocp_tables" not in eafit["overrides"]
    for key in eafit["overrides"]:
        assert "thickness" not in key
        assert "OCP" not in key


def test_preset_tables_are_a_deep_copy_of_the_canonical_tables():
    eafit = next(preset for preset in PRESETS if preset["id"] == "eafit")
    assert eafit["ocp_tables"] == EAFIT_OCP_TABLES
    assert eafit["ocp_tables"] is not EAFIT_OCP_TABLES
    assert eafit["ocp_tables"]["negative"] is not EAFIT_OCP_TABLES["negative"]
    assert eafit["ocp_tables"]["negative"][0] is not EAFIT_OCP_TABLES["negative"][0]
