"""Metadatos del conjunto Chayambuka2022, leídos de PyBaMM.

Los valores numéricos salen de ParameterValues. Las categorías siguen los
bloques del archivo upstream Chayambuka2022.py. No se inventan rangos de
ajuste: las cotas de abajo son restricciones físicas de signo y de fracción
volumétrica.
"""

from __future__ import annotations

import pybamm

from backend.errors import AppError
from backend.models.registry import require_implemented

# Grupos del diccionario en Chayambuka2022.get_parameter_values.
CATEGORIES: dict[str, str] = {
    "Negative electrode thickness [m]": "Celda",
    "Separator thickness [m]": "Celda",
    "Positive electrode thickness [m]": "Celda",
    "Electrode height [m]": "Celda",
    "Electrode width [m]": "Celda",
    "Nominal cell capacity [A.h]": "Celda",
    "Current function [A]": "Celda",
    "Contact resistance [Ohm]": "Celda",
    "Negative electrode conductivity [S.m-1]": "Electrodo negativo",
    "Maximum concentration in negative electrode [mol.m-3]": "Electrodo negativo",
    "Negative particle diffusivity [m2.s-1]": "Electrodo negativo",
    "Negative electrode OCP [V]": "Electrodo negativo",
    "Negative electrode porosity": "Electrodo negativo",
    "Negative electrode active material volume fraction": "Electrodo negativo",
    "Negative particle radius [m]": "Electrodo negativo",
    "Negative electrode Bruggeman coefficient (electrolyte)": "Electrodo negativo",
    "Negative electrode Bruggeman coefficient (electrode)": "Electrodo negativo",
    "Negative electrode charge transfer coefficient": "Electrodo negativo",
    "Negative electrode exchange-current density [A.m-2]": "Electrodo negativo",
    "Negative electrode OCP entropic change [V.K-1]": "Electrodo negativo",
    "Positive electrode conductivity [S.m-1]": "Electrodo positivo",
    "Maximum concentration in positive electrode [mol.m-3]": "Electrodo positivo",
    "Positive particle diffusivity [m2.s-1]": "Electrodo positivo",
    "Positive electrode OCP [V]": "Electrodo positivo",
    "Positive electrode porosity": "Electrodo positivo",
    "Positive electrode active material volume fraction": "Electrodo positivo",
    "Positive particle radius [m]": "Electrodo positivo",
    "Positive electrode Bruggeman coefficient (electrolyte)": "Electrodo positivo",
    "Positive electrode Bruggeman coefficient (electrode)": "Electrodo positivo",
    "Positive electrode charge transfer coefficient": "Electrodo positivo",
    "Positive electrode exchange-current density [A.m-2]": "Electrodo positivo",
    "Positive electrode OCP entropic change [V.K-1]": "Electrodo positivo",
    "Separator porosity": "Separador",
    "Separator Bruggeman coefficient (electrolyte)": "Separador",
    "Initial concentration in electrolyte [mol.m-3]": "Electrolito",
    "Cation transference number": "Electrolito",
    "Thermodynamic factor": "Electrolito",
    "Electrolyte diffusivity [m2.s-1]": "Electrolito",
    "Electrolyte conductivity [S.m-1]": "Electrolito",
    "Reference temperature [K]": "Experimento",
    "Ambient temperature [K]": "Experimento",
    "Number of electrodes connected in parallel to make a cell": "Experimento",
    "Number of cells connected in series to make a battery": "Experimento",
    "Lower voltage cut-off [V]": "Experimento",
    "Upper voltage cut-off [V]": "Experimento",
    "Open-circuit voltage at 0% SOC [V]": "Experimento",
    "Open-circuit voltage at 100% SOC [V]": "Experimento",
    "Initial concentration in negative electrode [mol.m-3]": "Experimento",
    "Initial concentration in positive electrode [mol.m-3]": "Experimento",
    "Initial temperature [K]": "Experimento",
}

# Comprobado numéricamente: cambiarlos no modifica Voltage [V] en un
# discharge de 30 s con BasicDFN. Ver docs/decisiones_cientificas.md.
DOES_NOT_AFFECT_BASIC_DFN = {
    "Contact resistance [Ohm]": (
        "Está en el conjunto Chayambuka2022. BasicDFN define Voltage [V] como "
        "el potencial del sólido positivo en el colector y no resta I·R."
    ),
    "Ambient temperature [K]": (
        "BasicDFN fija T = Initial temperature [K]. No resuelve intercambio "
        "térmico con el ambiente."
    ),
    "Open-circuit voltage at 0% SOC [V]": (
        "No entra en las ecuaciones ni en los eventos de BasicDFN. El corte "
        "de voltaje usa Lower voltage cut-off [V]."
    ),
    "Open-circuit voltage at 100% SOC [V]": (
        "No entra en las ecuaciones ni en los eventos de BasicDFN. El corte "
        "de voltaje usa Upper voltage cut-off [V]."
    ),
    "Nominal cell capacity [A.h]": (
        "No aparece en los residuales del DFN. Esta aplicación sí lo usa "
        "para convertir C-rate en corriente: I [A] = C-rate × capacidad [A.h], "
        "y para validar el límite de corriente de 50 C."
    ),
}

NOTES = {
    "Current function [A]": (
        "Lo fija la condición eléctrica del experimento. Corriente positiva "
        "es descarga."
    ),
    "Initial temperature [K]": (
        "Temperatura isotérmica impuesta. Entra en Butler-Volmer como "
        "F·η/(R·T) y, si el cambio entrópico no es cero, en el OCP. No es "
        "una variable resuelta."
    ),
    "Reference temperature [K]": (
        "Entra solo en el término (T − T_ref)·dU/dT. Con el cambio entrópico "
        "publicado (0) no modifica la solución."
    ),
    "Negative electrode OCP entropic change [V.K-1]": (
        "El conjunto lo trae en 0. Si se cambia, PyBaMM lo suma al OCP como "
        "(T − T_ref)·dU/dT."
    ),
    "Positive electrode OCP entropic change [V.K-1]": (
        "El conjunto lo trae en 0. Si se cambia, PyBaMM lo suma al OCP como "
        "(T − T_ref)·dU/dT."
    ),
    "Negative electrode Bruggeman coefficient (electrode)": (
        "El valor publicado es 0. La conductividad efectiva del sólido queda "
        "σ·ε^0 = σ."
    ),
    "Positive electrode Bruggeman coefficient (electrode)": (
        "El valor publicado es 0. La conductividad efectiva del sólido queda "
        "σ·ε^0 = σ."
    ),
    "Number of cells connected in series to make a battery": (
        "Escala Battery voltage [V]. No cambia Voltage [V] de la celda."
    ),
    "Negative electrode active material volume fraction": (
        "En el conjunto, 1 − porosidad − 0.001. La suma de porosidad y "
        "fracción activa tiene que ser ≤ 1."
    ),
    "Positive electrode active material volume fraction": (
        "En el conjunto, 1 − 0.23 − 0.22. La fracción inactiva no es un "
        "parámetro aparte."
    ),
}

CATEGORY_ORDER = [
    "Celda",
    "Electrodo negativo",
    "Electrodo positivo",
    "Separador",
    "Electrolito",
    "Experimento",
]

# Cotas físicas. gt/ge/lt/le son inclusivas o estrictas según la clave.
# No son intervalos de calibración del artículo.
CONSTRAINTS: dict[str, dict] = {
    "Negative electrode thickness [m]": {"gt": 0},
    "Separator thickness [m]": {"gt": 0},
    "Positive electrode thickness [m]": {"gt": 0},
    "Electrode height [m]": {"gt": 0},
    "Electrode width [m]": {"gt": 0},
    "Nominal cell capacity [A.h]": {"gt": 0},
    "Contact resistance [Ohm]": {"ge": 0},
    "Negative electrode conductivity [S.m-1]": {"gt": 0},
    "Maximum concentration in negative electrode [mol.m-3]": {"gt": 0},
    "Negative electrode porosity": {"gt": 0, "lt": 1},
    "Negative electrode active material volume fraction": {"gt": 0, "lt": 1},
    "Negative particle radius [m]": {"gt": 0},
    "Negative electrode Bruggeman coefficient (electrolyte)": {"ge": 0},
    "Negative electrode Bruggeman coefficient (electrode)": {"ge": 0},
    "Negative electrode charge transfer coefficient": {"gt": 0, "lt": 1},
    "Negative electrode OCP entropic change [V.K-1]": {},
    "Positive electrode conductivity [S.m-1]": {"gt": 0},
    "Maximum concentration in positive electrode [mol.m-3]": {"gt": 0},
    "Positive electrode porosity": {"gt": 0, "lt": 1},
    "Positive electrode active material volume fraction": {"gt": 0, "lt": 1},
    "Positive particle radius [m]": {"gt": 0},
    "Positive electrode Bruggeman coefficient (electrolyte)": {"ge": 0},
    "Positive electrode Bruggeman coefficient (electrode)": {"ge": 0},
    "Positive electrode charge transfer coefficient": {"gt": 0, "lt": 1},
    "Positive electrode OCP entropic change [V.K-1]": {},
    "Separator porosity": {"gt": 0, "lt": 1},
    "Separator Bruggeman coefficient (electrolyte)": {"ge": 0},
    "Initial concentration in electrolyte [mol.m-3]": {"gt": 0},
    "Cation transference number": {"gt": 0, "lt": 1},
    "Thermodynamic factor": {"gt": 0},
    "Reference temperature [K]": {"gt": 0},
    "Ambient temperature [K]": {"gt": 0},
    "Number of electrodes connected in parallel to make a cell": {"ge": 1},
    "Number of cells connected in series to make a battery": {"ge": 1},
    "Lower voltage cut-off [V]": {"gt": 0},
    "Upper voltage cut-off [V]": {"gt": 0},
    "Open-circuit voltage at 0% SOC [V]": {},
    "Open-circuit voltage at 100% SOC [V]": {},
    "Initial concentration in negative electrode [mol.m-3]": {"gt": 0},
    "Initial concentration in positive electrode [mol.m-3]": {"gt": 0},
    "Initial temperature [K]": {"gt": 0},
}

# La corriente del experimento sustituye a este parámetro.
EXPERIMENT_OWNED = {"Current function [A]", "Initial temperature [K]"}


def default_parameter_values() -> pybamm.ParameterValues:
    return pybamm.ParameterValues("Chayambuka2022")


def unit_of(name: str) -> str | None:
    if name.endswith("]") and "[" in name:
        return name[name.rfind("[") + 1 : -1]
    return None


def _function_summary(fn) -> str:
    doc = (getattr(fn, "__doc__", None) or "").strip()
    if not doc:
        return getattr(fn, "__name__", "función")
    paragraph = doc.split("\n\n")[0]
    return " ".join(paragraph.split())


def list_parameters(model_id: str) -> dict:
    require_implemented(model_id)
    values = default_parameter_values()
    items = []
    for name, value in values.items():
        if name == "citations":
            continue
        kind = "function" if callable(value) else "number"
        if kind == "number" and isinstance(value, bool):
            kind = "other"
        elif kind == "number" and not isinstance(value, (int, float)):
            kind = "other"
        unused_note = DOES_NOT_AFFECT_BASIC_DFN.get(name)
        record = {
            "name": name,
            "unit": unit_of(name),
            "category": CATEGORIES.get(name, "Sin clasificar"),
            "type": kind,
            "editable": kind == "number" and name not in EXPERIMENT_OWNED,
            "affects_basic_dfn": name not in DOES_NOT_AFFECT_BASIC_DFN
            and kind == "number",
            "original": float(value) if kind == "number" else None,
            "constraints": CONSTRAINTS.get(name, {}) if kind == "number" else {},
            "description": NOTES.get(name) or unused_note or "",
            "function_summary": _function_summary(value) if kind == "function" else None,
        }
        if name in EXPERIMENT_OWNED:
            record["affects_basic_dfn"] = True
            record["description"] = NOTES.get(name, "")
        if unused_note and name not in NOTES:
            record["description"] = unused_note
        items.append(record)
    items.sort(key=lambda row: (CATEGORY_ORDER.index(row["category"]) if row["category"] in CATEGORY_ORDER else 99, row["name"]))
    citations = list(values.get("citations", []))
    return {
        "model": model_id,
        "parameter_set": "Chayambuka2022",
        "categories": CATEGORY_ORDER,
        "citations": citations,
        "parameters": items,
    }


def original_numbers() -> dict[str, float]:
    values = default_parameter_values()
    out = {}
    for name, value in values.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[name] = float(value)
    return out


def ensure_known_model(model_id: str) -> None:
    try:
        require_implemented(model_id)
    except AppError:
        raise
