"""Validación. El backend es la autoridad: el cliente solo adelanta estas reglas."""

from __future__ import annotations

import math

from backend.parameters.catalogue import (
    CATEGORIES,
    CONSTRAINTS,
    DOES_NOT_AFFECT_BASIC_DFN,
    EXPERIMENT_OWNED,
    original_numbers,
)

MAX_DURATION_S = 6 * 3600
MAX_C_RATE = 50.0
TEMPERATURE_WARN = (250.0, 350.0)


def _finite_number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _bound_message(name: str, rule: str, limit: float) -> str:
    words = {
        "gt": f"tiene que ser > {limit}",
        "ge": f"tiene que ser ≥ {limit}",
        "lt": f"tiene que ser < {limit}",
        "le": f"tiene que ser ≤ {limit}",
    }
    return f"{name}: {words[rule]}."


def validate_overrides(overrides: dict) -> tuple[dict[str, float], list[str], list[str]]:
    """Devuelve (valores fusionados, errores, avisos)."""
    originals = original_numbers()
    errors: list[str] = []
    warnings: list[str] = []
    merged = dict(originals)

    if not isinstance(overrides, dict):
        return merged, ["parameters tiene que ser un objeto de números."], warnings

    for name, raw in overrides.items():
        if name not in CATEGORIES:
            errors.append(f"Parámetro desconocido: {name}.")
            continue
        if name not in originals:
            errors.append(
                f"{name} es una función del conjunto de parámetros. No se sustituye por un número."
            )
            continue
        if name in EXPERIMENT_OWNED:
            errors.append(
                f"{name} lo fija el experimento (corriente o temperatura), no el mapa de parámetros."
            )
            continue
        if name not in originals:
            errors.append(f"{name} no es un parámetro numérico editable.")
            continue
        number = _finite_number(raw)
        if number is None:
            errors.append(f"{name}: se esperaba un número finito en la unidad del parámetro.")
            continue
        for rule, limit in CONSTRAINTS.get(name, {}).items():
            ok = {
                "gt": number > limit,
                "ge": number >= limit,
                "lt": number < limit,
                "le": number <= limit,
            }[rule]
            if not ok:
                errors.append(_bound_message(name, rule, limit))
        merged[name] = number
        if name in DOES_NOT_AFFECT_BASIC_DFN and number != originals[name]:
            warnings.append(
                f"{name} cambió de {originals[name]} a {number}. {DOES_NOT_AFFECT_BASIC_DFN[name]}"
            )

    _volume_fraction(merged, "Negative", errors)
    _volume_fraction(merged, "Positive", errors)
    _concentration_cap(
        merged,
        "Initial concentration in negative electrode [mol.m-3]",
        "Maximum concentration in negative electrode [mol.m-3]",
        errors,
    )
    _concentration_cap(
        merged,
        "Initial concentration in positive electrode [mol.m-3]",
        "Maximum concentration in positive electrode [mol.m-3]",
        errors,
    )
    lower = merged["Lower voltage cut-off [V]"]
    upper = merged["Upper voltage cut-off [V]"]
    if lower >= upper:
        errors.append(
            "Lower voltage cut-off [V] tiene que ser menor que Upper voltage cut-off [V]."
        )
    return merged, errors, warnings


def _volume_fraction(merged: dict[str, float], side: str, errors: list[str]) -> None:
    porosity = merged[f"{side} electrode porosity"]
    active = merged[f"{side} electrode active material volume fraction"]
    if porosity + active > 1:
        errors.append(
            f"{side} electrode: porosidad ({porosity}) + fracción activa ({active}) = "
            f"{porosity + active} > 1. No queda fracción para el material inactivo."
        )


def _concentration_cap(merged, initial_key, maximum_key, errors) -> None:
    if merged[initial_key] > merged[maximum_key]:
        errors.append(
            f"{initial_key} ({merged[initial_key]}) supera {maximum_key} ({merged[maximum_key]})."
        )


def resolve_current(experiment: dict, nominal_capacity_ah: float) -> tuple[float | None, list[str]]:
    mode = experiment.get("current_mode", "current")
    errors: list[str] = []
    if mode == "c_rate":
        rate = _finite_number(experiment.get("c_rate"))
        if rate is None or rate <= 0:
            errors.append("c_rate tiene que ser un número > 0.")
            return None, errors
        if rate > MAX_C_RATE:
            errors.append(
                f"c_rate = {rate} supera el límite de la aplicación ({MAX_C_RATE}). "
                "No es un límite de PyBaMM: a 1 C el interpolante k_n ya extrapola."
            )
            return None, errors
        return rate * nominal_capacity_ah, errors
    if mode == "current":
        current = _finite_number(experiment.get("current_A"))
        if current is None or current == 0:
            errors.append("current_A tiene que ser un número distinto de cero. El signo lo pone el tipo de experimento.")
            return None, errors
        if current < 0:
            errors.append(
                "current_A es la magnitud. Use type 'charge' para corriente negativa."
            )
            return None, errors
        limit = MAX_C_RATE * nominal_capacity_ah
        if current > limit:
            errors.append(
                f"current_A = {current} A supera {MAX_C_RATE} C para la capacidad nominal actual ({nominal_capacity_ah} A.h)."
            )
            return None, errors
        return current, errors
    errors.append("current_mode tiene que ser 'current' o 'c_rate'.")
    return None, errors


def validate_experiment(experiment: dict, merged: dict[str, float]) -> tuple[dict | None, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(experiment, dict):
        return None, ["experiment tiene que ser un objeto."], warnings

    kind = experiment.get("type")
    if kind not in {"discharge", "charge", "cycle"}:
        errors.append("experiment.type tiene que ser discharge, charge o cycle.")
        return None, errors, warnings

    temperature = _finite_number(experiment.get("temperature_K"))
    if temperature is None or temperature <= 0:
        errors.append("temperature_K tiene que ser un número > 0, en kelvin.")
    elif not TEMPERATURE_WARN[0] <= temperature <= TEMPERATURE_WARN[1]:
        warnings.append(
            f"temperature_K = {temperature} K está fuera de {TEMPERATURE_WARN[0]}–{TEMPERATURE_WARN[1]} K. "
            "Las funciones de Chayambuka2022 no dependen de T; solo cambian Butler-Volmer y, si se editó, el término entrópico."
        )

    magnitude, current_errors = resolve_current(experiment, merged["Nominal cell capacity [A.h]"])
    errors.extend(current_errors)

    duration = None
    discharge_s = None
    charge_s = None
    if kind in {"discharge", "charge"}:
        duration = _finite_number(experiment.get("duration_s"))
        if duration is None or duration <= 0:
            errors.append("duration_s tiene que ser un número > 0.")
        elif duration > MAX_DURATION_S:
            errors.append(f"duration_s supera el límite de la aplicación ({MAX_DURATION_S} s).")
    else:
        discharge_s = _finite_number(experiment.get("discharge_duration_s"))
        charge_s = _finite_number(experiment.get("charge_duration_s"))
        if discharge_s is None or discharge_s <= 0:
            errors.append("discharge_duration_s tiene que ser un número > 0.")
        if charge_s is None or charge_s <= 0:
            errors.append("charge_duration_s tiene que ser un número > 0.")
        if discharge_s and charge_s and discharge_s + charge_s > MAX_DURATION_S:
            errors.append(
                f"La duración del ciclo supera el límite de la aplicación ({MAX_DURATION_S} s)."
            )
        if discharge_s and charge_s:
            duration = discharge_s + charge_s

    if errors or magnitude is None or temperature is None or duration is None:
        return None, errors, warnings

    signed = magnitude if kind == "discharge" else -magnitude if kind == "charge" else magnitude
    spec = {
        "type": kind,
        "current_magnitude_A": magnitude,
        "signed_current_A": signed,
        "temperature_K": temperature,
        "duration_s": duration,
        "discharge_duration_s": discharge_s,
        "charge_duration_s": charge_s,
    }
    return spec, errors, warnings
