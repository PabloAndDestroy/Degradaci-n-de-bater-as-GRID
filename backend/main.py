import pybamm
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.routes import router
from backend.errors import AppError

pybamm.set_logging_level("ERROR")

app = FastAPI(
    title="Parametrización de baterías",
    version="0.1.0",
    summary="Capa de parámetros, ejecución y resultados sobre PyBaMM.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(AppError)
async def handle_app_error(_request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "details": exc.details or []},
    )


@app.exception_handler(Exception)
async def handle_unexpected(_request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "La simulación no pudo completarse.",
            "details": [f"{type(exc).__name__}: {exc}"],
        },
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "pybamm": pybamm.__version__}
