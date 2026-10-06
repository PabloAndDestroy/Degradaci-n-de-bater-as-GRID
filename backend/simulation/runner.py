"""Carga BasicDFN, aplica parámetros y resuelve con el solver de PyBaMM."""

from __future__ import annotations

import time
import warnings

import numpy as np
import pybamm

from backend.errors import AppError
from backend.models.registry import require_implemented
from backend.parameters.catalogue import default_parameter_values
from backend.simulation.outputs import DEFAULT_SERIES, attach_reductions, list_variables
from backend.validation.checks import validate_experiment, validate_overrides

MAX_POINTS = 2000


def build_model(model_id: str):
    require_implemented(model_id)
    model = pybamm.sodium_ion.BasicDFN()
    attach_reductions(model)
    return model


def variable_catalogue(model_id: str) -> dict:
    model = build_model(model_id)
    return {
        "model": model_id,
        "variables": list_variables(model),
        "default_series": DEFAULT_SERIES,
        "not_available": [
            {
                "name": "Temperature [K]",
                "reason": "BasicDFN no resuelve la temperatura. Initial temperature [K] es un dato constante.",
            },
            {
                "name": "Resistance [Ohm]",
                "reason": "BasicDFN no define una resistencia. No se calcula V/I ni se usa Contact resistance [Ohm], porque ese parámetro no entra en Voltage [V].",
            },
            {
                "name": "State of charge",
                "reason": "BasicDFN no tiene una variable de SOC. Los parámetros Open-circuit voltage at 0% SOC y at 100% SOC no entran en el modelo.",
            },
            {
                "name": "Degradation",
                "reason": "BasicDFN no incluye SEI, plating ni pérdida de material activo.",
            },
        ],
    }


def _current_symbol(spec: dict):
    magnitude = spec["current_magnitude_A"]
    if spec["type"] == "discharge":
        return magnitude
    if spec["type"] == "charge":
        return -magnitude
    t_switch = spec["discharge_duration_s"]

    def current(t):
        # Forma con Heaviside: PyBaMM no acepta un if de Python sobre el símbolo t.
        return magnitude * (t < t_switch) - magnitude * (t >= t_switch)

    return current


def prepare(model_id: str, overrides: dict, experiment: dict):
    require_implemented(model_id)
    merged, errors, warnings_out = validate_overrides(overrides or {})
    spec, exp_errors, exp_warnings = validate_experiment(experiment or {}, merged)
    errors.extend(exp_errors)
    warnings_out.extend(exp_warnings)
    if errors or spec is None:
        return None, errors, warnings_out

    parameter_values = default_parameter_values()
    numeric_updates = {
        name: merged[name]
        for name in merged
        if name not in {"Current function [A]", "Initial temperature [K]"}
    }
    parameter_values.update(numeric_updates)
    parameter_values.update(
        {
            "Initial temperature [K]": spec["temperature_K"],
            "Current function [A]": _current_symbol(spec),
        }
    )
    return (parameter_values, spec, merged), errors, warnings_out


def _as_series(values) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim == 0:
        return array.reshape(1)
    return array.ravel()


def _thin_index(n: int) -> np.ndarray:
    if n <= MAX_POINTS:
        return np.arange(n)
    index = np.linspace(0, n - 1, MAX_POINTS).astype(int)
    index[0] = 0
    index[-1] = n - 1
    return np.unique(index)


def _series_meta(name: str) -> dict:
    from backend.simulation.outputs import reduction_note

    note = reduction_note(name)
    unit = None
    if name.endswith("]") and "[" in name:
        unit = name[name.rfind("[") + 1 : -1]
    return {
        "unit": unit,
        "source": "reduction" if note else "model",
        "description": note or "",
    }


def simulate(
    model_id: str,
    overrides: dict,
    experiment: dict,
    variables: list[str] | None = None,
    label: str | None = None,
) -> dict:
    prepared, errors, warning_messages = prepare(model_id, overrides, experiment)
    if prepared is None:
        raise AppError("La configuración no es válida.", status_code=422, details=errors)

    parameter_values, spec, _merged = prepared
    requested = list(variables) if variables else list(DEFAULT_SERIES)
    if "Time [s]" not in requested:
        requested = ["Time [s]", *requested]

    model = build_model(model_id)
    known = set(model.variables)
    unknown = [name for name in requested if name not in known]
    if unknown:
        raise AppError(
            "Hay variables que este modelo no expone.",
            status_code=422,
            details=[f"Variable desconocida: {name}." for name in unknown],
        )
    spatial = []
    catalogue = {row["name"]: row for row in list_variables(model)}
    for name in requested:
        row = catalogue[name]
        if not row["plottable"]:
            spatial.append(f"{name}: {row['reason']}")
    if spatial:
        raise AppError(
            "Esas variables no son series temporales.",
            status_code=422,
            details=spatial,
        )

    simulation = pybamm.Simulation(
        model,
        parameter_values=parameter_values,
        solver=pybamm.IDAKLUSolver(),
    )
    started = time.perf_counter()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", pybamm.SolverWarning)
        try:
            solution = simulation.solve([0, spec["duration_s"]])
        except pybamm.SolverError as exc:
            message = "PyBaMM no pudo resolver la simulación."
            details = [str(exc)]
            solver_error = str(exc)
            if (
                spec["type"] == "charge"
                and "Maximum voltage [V]" in solver_error
                and "non-positive at initial conditions" in solver_error
            ):
                message = (
                    "No se puede iniciar la carga con estas condiciones iniciales "
                    "y esta corriente."
                )
                details = [
                    "La condición inicial activa el límite superior de voltaje antes "
                    "de que PyBaMM pueda comenzar la integración.",
                    "Reduzca el C-rate o use un estado inicial más descargado. También "
                    "puede ejecutar un ciclo descarga/carga, que empieza descargando.",
                    solver_error,
                ]
            raise AppError(
                message,
                status_code=422,
                details=details,
            ) from exc
    elapsed = time.perf_counter() - started

    for item in caught:
        text = str(item.message).strip()
        if text and text not in warning_messages:
            warning_messages.append(text)

    time_values = _as_series(solution["Time [s]"].entries)
    if time_values.size == 0 or not np.all(np.isfinite(time_values)):
        raise AppError("La solución no trae un vector de tiempo utilizable.", status_code=422)

    index = _thin_index(time_values.size)
    series = {}
    meta = {}
    for name in requested:
        column = _as_series(solution[name].entries)
        if column.shape != time_values.shape:
            raise AppError(
                f"La variable '{name}' no tiene la misma longitud que el tiempo.",
                status_code=422,
                details=[f"time={time_values.shape}, {name}={column.shape}"],
            )
        if not np.all(np.isfinite(column)):
            raise AppError(
                f"La variable '{name}' contiene valores no finitos.",
                status_code=422,
            )
        series[name] = column[index].tolist()
        meta[name] = _series_meta(name)

    termination = solution.termination
    return {
        "label": label or spec["type"],
        "model": model_id,
        "parameter_set": "Chayambuka2022",
        "solver": "IDAKLUSolver",
        "termination": termination,
        "warnings": warning_messages,
        "elapsed_s": elapsed,
        "n_solver_points": int(time_values.size),
        "n_points": int(index.size),
        "downsampled": bool(index.size != time_values.size),
        "applied": {
            "type": spec["type"],
            "current_magnitude_A": spec["current_magnitude_A"],
            "temperature_K": spec["temperature_K"],
            "duration_requested_s": spec["duration_s"],
            "t_end_s": float(time_values[-1]),
            "sign_convention": "Corriente positiva = descarga.",
        },
        "series": series,
        "series_meta": meta,
    }
