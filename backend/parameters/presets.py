"""Presets de parámetros por modelo.

El conjunto base es siempre Chayambuka2022. Los presets no cargan Excel ni
inventan números: solo agrupan overrides y el experimento asociado.
"""

from __future__ import annotations

from copy import deepcopy

from backend.models.registry import require_implemented
from backend.parameters.ocp_tables import EAFIT_OCP_TABLES

EAFIT_NOTE = (
    "La geometría (espesores, altura, ancho, porosidad y Bruggeman del "
    "separador, OCV) no está en la columna Celda EAFIT y sigue en "
    "Chayambuka2022. 75 Ah y 24.75 A no reescalan el área."
)

PRESETS = [
    {
        "id": "chayambuka",
        "label": "Chayambuka2022",
        "parameter_set": "Chayambuka2022",
        "overrides": {},
        "experiment": None,
    },
    {
        "id": "eafit",
        "label": "EAFIT",
        "parameter_set": "Chayambuka2022",
        "overrides": {
            "Nominal cell capacity [A.h]": 75,
            "Contact resistance [Ohm]": 0,
            "Reference temperature [K]": 298.15,
            "Ambient temperature [K]": 298.15,
            "Number of electrodes connected in parallel to make a cell": 1,
            "Number of cells connected in series to make a battery": 1,
            "Lower voltage cut-off [V]": 1.5,
            "Upper voltage cut-off [V]": 3.9,
        },
        "experiment": {
            "current_mode": "current",
            "current_A": 24.75,
            "temperature_K": 298.15,
        },
        "ocp_tables": deepcopy(EAFIT_OCP_TABLES),
        "note": EAFIT_NOTE,
    },
]


def list_presets(model_id: str) -> list[dict]:
    require_implemented(model_id)
    return [deepcopy(preset) for preset in PRESETS]
