"""Tablas OCP opcionales para BasicDFN.

Las tablas son un dato opcional, hermano de los overrides numéricos. Si no se
entrega una tabla para un electrodo, ese OCP sigue siendo la función de
Chayambuka2022. Si se entrega, se valida y se sustituye por un interpolante
lineal. No se inventan puntos.
"""

from __future__ import annotations

import math

import numpy as np
import pybamm

# Puntos canónicos EAFIT. Públicos: el slice de presets los reexporta.
EAFIT_OCP_TABLES = {
    "negative": [
        {"sto": 0.0, "V": 1.30},
        {"sto": 0.05, "V": 0.95},
        {"sto": 0.10, "V": 0.78},
        {"sto": 0.15, "V": 0.63},
        {"sto": 0.20, "V": 0.50},
        {"sto": 0.25, "V": 0.36},
        {"sto": 0.30, "V": 0.24},
        {"sto": 0.35, "V": 0.15},
        {"sto": 0.40, "V": 0.10},
        {"sto": 0.45, "V": 0.07},
        {"sto": 0.50, "V": 0.06},
        {"sto": 0.55, "V": 0.06},
        {"sto": 0.60, "V": 0.06},
        {"sto": 0.65, "V": 0.06},
        {"sto": 0.70, "V": 0.06},
        {"sto": 0.75, "V": 0.04},
        {"sto": 0.80, "V": 0.04},
        {"sto": 0.85, "V": 0.04},
        {"sto": 0.90, "V": 0.04},
        {"sto": 0.95, "V": 0.03},
        {"sto": 1.00, "V": 0.03},
    ],
    "positive": [
        {"sto": 0.17, "V": 3.95},
        {"sto": 0.20, "V": 3.87},
        {"sto": 0.25, "V": 3.78},
        {"sto": 0.30, "V": 3.68},
        {"sto": 0.35, "V": 3.58},
        {"sto": 0.40, "V": 3.48},
        {"sto": 0.45, "V": 3.38},
        {"sto": 0.50, "V": 3.28},
        {"sto": 0.55, "V": 3.18},
        {"sto": 0.60, "V": 3.08},
        {"sto": 0.65, "V": 2.99},
        {"sto": 0.70, "V": 2.94},
        {"sto": 0.75, "V": 2.92},
        {"sto": 0.80, "V": 2.92},
        {"sto": 0.85, "V": 2.91},
        {"sto": 0.90, "V": 2.90},
        {"sto": 0.95, "V": 2.85},
        {"sto": 1.00, "V": 2.30},
    ],
}

ELECTRODES = {
    "negative": "Negative electrode OCP [V]",
    "positive": "Positive electrode OCP [V]",
}


def _finite_number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def validate_ocp_tables(ocp_tables) -> list[str]:
    """Devuelve errores de texto. Una lista vacía o ausente no es error."""
    errors: list[str] = []
    if ocp_tables is None:
        return errors
    if not isinstance(ocp_tables, dict):
        return ["ocp_tables tiene que ser un objeto con claves 'negative' y 'positive'."]

    for name in ocp_tables:
        if name not in ELECTRODES:
            errors.append(f"ocp_tables: electrodo desconocido '{name}'. Use 'negative' o 'positive'.")

    for electrode in ELECTRODES:
        points = ocp_tables.get(electrode)
        if points is None:
            continue
        if not isinstance(points, list):
            errors.append(f"ocp_tables.{electrode} tiene que ser una lista de puntos {{sto, V}}.")
            continue
        if len(points) == 0:
            continue
        if len(points) < 2:
            errors.append(
                f"ocp_tables.{electrode} necesita al menos 2 puntos; llegaron {len(points)}."
            )
            continue

        sto_values: list[float] = []
        valid = True
        for index, point in enumerate(points):
            if not isinstance(point, dict):
                errors.append(
                    f"ocp_tables.{electrode}[{index}] tiene que ser un objeto con sto y V."
                )
                valid = False
                continue
            sto = _finite_number(point.get("sto"))
            voltage = _finite_number(point.get("V"))
            if sto is None:
                errors.append(
                    f"ocp_tables.{electrode}[{index}].sto tiene que ser un número finito."
                )
                valid = False
            if voltage is None:
                errors.append(
                    f"ocp_tables.{electrode}[{index}].V tiene que ser un número finito."
                )
                valid = False
            if sto is not None:
                sto_values.append(sto)

        if not valid or len(sto_values) != len(points):
            continue
        for previous, current in zip(sto_values, sto_values[1:]):
            if not current > previous:
                errors.append(
                    f"ocp_tables.{electrode}: sto tiene que ser estrictamente creciente "
                    f"({previous} seguido de {current})."
                )
                break

    return errors


def ocp_interpolant(points):
    """Devuelve un callable(sto) que construye un pybamm.Interpolant lineal."""
    sto = np.asarray([point["sto"] for point in points], dtype=float)
    voltage = np.asarray([point["V"] for point in points], dtype=float)

    def ocp(sto_value):
        return pybamm.Interpolant(sto, voltage, sto_value, "EAFIT OCP")

    return ocp
