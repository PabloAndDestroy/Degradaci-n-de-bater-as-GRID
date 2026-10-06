from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.errors import AppError
from backend.models.registry import MODELS, get_model_info
from backend.parameters.catalogue import list_parameters
from backend.simulation.runner import simulate, variable_catalogue
from backend.validation.checks import validate_experiment, validate_overrides

router = APIRouter(prefix="/api")
CONFIGURATIONS: dict[str, dict] = {}


class ExperimentIn(BaseModel):
    type: Literal["discharge", "charge", "cycle"]
    current_mode: Literal["current", "c_rate"] = "current"
    current_A: float | None = None
    c_rate: float | None = None
    duration_s: float | None = None
    discharge_duration_s: float | None = None
    charge_duration_s: float | None = None
    temperature_K: float = 298.15


class SimulateIn(BaseModel):
    model: str = "sodium_ion"
    parameters: dict[str, Any] = Field(default_factory=dict)
    experiment: ExperimentIn
    variables: list[str] | None = None
    label: str | None = None


class CompareIn(BaseModel):
    cases: list[SimulateIn]


class ValidateIn(BaseModel):
    model: str = "sodium_ion"
    parameters: dict[str, Any] = Field(default_factory=dict)
    experiment: ExperimentIn | None = None


class ConfigurationIn(BaseModel):
    name: str
    model: str = "sodium_ion"
    parameters: dict[str, Any] = Field(default_factory=dict)
    experiment: ExperimentIn


def _check(body: ValidateIn) -> dict:
    get_model_info(body.model)
    merged, errors, warnings = validate_overrides(body.parameters)
    if body.experiment is not None:
        _spec, exp_errors, exp_warnings = validate_experiment(
            body.experiment.model_dump(), merged
        )
        errors.extend(exp_errors)
        warnings.extend(exp_warnings)
    return {"valid": not errors, "errors": errors, "warnings": warnings}


@router.get("/models")
def get_models():
    return {"models": MODELS}


@router.get("/models/{model_id}")
def get_model(model_id: str):
    return get_model_info(model_id)


@router.get("/models/{model_id}/parameters")
def get_parameters(model_id: str):
    return list_parameters(model_id)


@router.get("/models/{model_id}/variables")
def get_variables(model_id: str):
    return variable_catalogue(model_id)


@router.post("/parameters/validate")
def post_validate(body: ValidateIn):
    if body.model != "sodium_ion":
        info = get_model_info(body.model)
        if not info["implemented"]:
            raise AppError(
                f"El modelo '{body.model}' está reservado y todavía no tiene simulación.",
                status_code=400,
            )
    return _check(body)


@router.post("/simulate")
def post_simulate(body: SimulateIn):
    return simulate(
        body.model,
        body.parameters,
        body.experiment.model_dump(),
        body.variables,
        body.label,
    )


@router.post("/simulate/compare")
def post_compare(body: CompareIn):
    if not body.cases:
        raise AppError("Hace falta al menos un caso.", status_code=422)
    if len(body.cases) > 4:
        raise AppError("La comparación acepta como máximo 4 casos.", status_code=422)
    results = []
    for index, case in enumerate(body.cases, start=1):
        label = case.label or f"Caso {index}"
        results.append(
            simulate(
                case.model,
                case.parameters,
                case.experiment.model_dump(),
                case.variables,
                label,
            )
        )
    return {"cases": results}


@router.get("/configurations")
def get_configurations():
    return {"configurations": list(CONFIGURATIONS.values())}


@router.post("/configurations")
def post_configuration(body: ConfigurationIn):
    name = body.name.strip()
    if not name or len(name) > 80:
        raise AppError("El nombre tiene que tener entre 1 y 80 caracteres.", status_code=422)
    get_model_info(body.model)
    stored = body.model_dump()
    stored["name"] = name
    CONFIGURATIONS[name] = stored
    return stored


@router.delete("/configurations/{name}")
def delete_configuration(name: str):
    if name not in CONFIGURATIONS:
        raise AppError(f"No hay una configuración llamada '{name}'.", status_code=404)
    del CONFIGURATIONS[name]
    return {"deleted": name}
