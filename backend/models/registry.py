"""Catálogo de modelos. Solo sodium-ion está conectado a PyBaMM."""

from backend.errors import AppError

IMPLEMENTED = "sodium_ion"

MODELS = [
    {
        "id": "sodium_ion",
        "name": "Sodium-ion",
        "implemented": True,
        "model_class": "pybamm.sodium_ion.BasicDFN",
        "parameter_set": "Chayambuka2022",
        "equations": "Doyle-Fuller-Newman (DFN)",
        "thermal": "isothermal",
        "degradation": None,
        "citation": "Chayambuka2022",
        "notes": [
            "BasicDFN usa las mismas ecuaciones DFN que el modelo de litio de Marquis et al., con el conjunto de parámetros de ion sodio Chayambuka2022.",
            "La temperatura es un dato (Initial temperature [K]), no una variable de estado. No hay ecuación térmica.",
            "No hay submodelos de degradación (SEI, plating, pérdida de material activo).",
            "No hay una variable de resistencia. Contact resistance [Ohm] está en el conjunto de parámetros y no entra en la expresión de Voltage [V].",
            "Corriente positiva significa descarga. Es la convención de PyBaMM.",
            "Las funciones de OCP, difusividad, conductividad y densidad de corriente de intercambio son interpolantes del conjunto. Esta aplicación no las sustituye por números.",
        ],
    },
    {
        "id": "lithium_ion",
        "name": "Lithium-ion",
        "implemented": False,
        "notes": ["Reservado. No está conectado a un modelo."],
    },
    {
        "id": "lfp",
        "name": "LFP",
        "implemented": False,
        "notes": ["Reservado. No está conectado a un modelo."],
    },
    {
        "id": "nmc",
        "name": "NMC",
        "implemented": False,
        "notes": ["Reservado. No está conectado a un modelo."],
    },
    {
        "id": "lead_acid",
        "name": "Lead-acid",
        "implemented": False,
        "notes": ["Reservado. No está conectado a un modelo."],
    },
]


def get_model_info(model_id: str) -> dict:
    for model in MODELS:
        if model["id"] == model_id:
            return model
    raise AppError(f"Modelo desconocido: {model_id}", status_code=404)


def require_implemented(model_id: str) -> dict:
    info = get_model_info(model_id)
    if not info["implemented"]:
        raise AppError(
            f"El modelo '{model_id}' está reservado y todavía no tiene simulación.",
            status_code=400,
        )
    return info
