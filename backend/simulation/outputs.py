"""Variables que la API puede devolver como series temporales.

Los promedios se añaden al modelo con operadores de PyBaMM antes de
discretizar. No son un promedio aritmético de los nodos a posteriori.
"""

from __future__ import annotations

import pybamm

# Alias que BasicDFN publica dos veces con el mismo símbolo.
HIDDEN_ALIASES = {
    "Current variable [A]": "Current [A]",
    "Voltage expression [V]": "Voltage [V]",
}

# (nombre publicado, variable del modelo, cómo se reduce)
REDUCTIONS = [
    (
        "Electrolyte concentration (x-average) [mol.m-3]",
        "Electrolyte concentration [mol.m-3]",
        "x",
    ),
    (
        "Electrolyte potential (x-average) [V]",
        "Electrolyte potential [V]",
        "x",
    ),
    (
        "Negative electrode potential (x-average) [V]",
        "Negative electrode potential [V]",
        "x",
    ),
    (
        "Positive electrode potential (x-average) [V]",
        "Positive electrode potential [V]",
        "x",
    ),
    (
        "Negative particle surface concentration (x-average) [mol.m-3]",
        "Negative particle surface concentration [mol.m-3]",
        "x",
    ),
    (
        "Positive particle surface concentration (x-average) [mol.m-3]",
        "Positive particle surface concentration [mol.m-3]",
        "x",
    ),
    (
        "Negative particle concentration (r-average, x-average) [mol.m-3]",
        "Negative particle concentration [mol.m-3]",
        "rx",
    ),
    (
        "Positive particle concentration (r-average, x-average) [mol.m-3]",
        "Positive particle concentration [mol.m-3]",
        "rx",
    ),
]


def _reduce(symbol, kind: str):
    if kind == "x":
        return pybamm.x_average(symbol)
    if kind == "rx":
        return pybamm.x_average(pybamm.r_average(symbol))
    raise ValueError(kind)


def attach_reductions(model) -> None:
    variables = model.variables
    for published, source, kind in REDUCTIONS:
        variables[published] = _reduce(variables[source], kind)


def reduction_note(name: str) -> str | None:
    for published, source, kind in REDUCTIONS:
        if published == name:
            operator = (
                "pybamm.x_average"
                if kind == "x"
                else "pybamm.x_average(pybamm.r_average(...))"
            )
            return (
                f"Reducción de '{source}' con {operator}, evaluada dentro del "
                "modelo antes de discretizar. r_average es el promedio en el "
                "volumen de la partícula que define PyBaMM; x_average es el "
                "promedio en el espesor del dominio."
            )
    return None


def is_spatial(symbol) -> bool:
    domains = getattr(symbol, "domains", None) or {}
    return any(domains.get(key) for key in ("primary", "secondary", "tertiary"))


def list_variables(model) -> list[dict]:
    rows = []
    for name, symbol in model.variables.items():
        if name in HIDDEN_ALIASES:
            rows.append(
                {
                    "name": name,
                    "plottable": False,
                    "reason": f"Alias de '{HIDDEN_ALIASES[name]}'. Es el mismo símbolo.",
                    "source": "model",
                }
            )
            continue
        note = reduction_note(name)
        spatial = is_spatial(symbol)
        rows.append(
            {
                "name": name,
                "plottable": not spatial,
                "reason": None
                if not spatial
                else "Campo espacial. Esta versión no lo envía; use la reducción promediada si existe.",
                "source": "reduction" if note else "model",
                "description": note or "",
            }
        )
    return rows


DEFAULT_SERIES = [
    "Voltage [V]",
    "Current [A]",
    "Discharge capacity [A.h]",
]
