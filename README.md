# Parametrización y análisis numérico de baterías

Aplicación web para elegir un modelo de batería, ver y modificar sus parámetros, simular con [PyBaMM](https://github.com/pybamm-team/PyBaMM) y comparar las curvas. La primera química conectada es ion sodio.

PyBaMM sigue siendo el modelo físico y el solver. Esta aplicación no reimplementa el DFN ni copia el repositorio de PyBaMM dentro del proyecto.

## Qué hay en el modelo de sodio

Inspección de PyBaMM 26.9.0, que es la versión fijada en `backend/requirements.txt`:

- El módulo `pybamm.sodium_ion` contiene una clase: `BasicDFN`.
- Es un Doyle–Fuller–Newman isotérmico. No trae opciones térmicas ni de degradación.
- El conjunto de parámetros por defecto es `Chayambuka2022` (hard carbon / NVPF / NaPF6 en EC:PC).
- Parte de los parámetros son números. OCP, difusividades, conductividad del electrolito y densidades de intercambio son funciones interpoladas. No se reemplazan por un escalar.
- `BasicDFN` no calcula temperatura, SOC ni resistencia. Esos huecos están documentados en la interfaz y en [docs/decisiones_cientificas.md](docs/decisiones_cientificas.md).

Las fuentes upstream, que no se modifican, son:

- modelo: `packages/pybamm/src/pybamm/models/full_battery_models/sodium_ion`
- parámetros: `packages/pybamm/src/pybamm/input/parameters/sodium_ion`

Las condiciones de entrada, casos límite, limitaciones del modelo y parámetros
que no conviene interpretar como controles físicos se describen en
[docs/condiciones_de_simulacion.md](docs/condiciones_de_simulacion.md).

## Arquitectura

```text
backend/            FastAPI. Carga PyBaMM, valida, resuelve y devuelve series.
frontend/           React. Parámetros, experimento, gráfica y comparación.
tests/              Pruebas del modelo, de la validación y de la API.
docs/               Decisiones que no son obvias al leer la interfaz.
```

No hay Docker, base de datos ni autenticación. Las configuraciones se guardan en un JSON descargado, en `localStorage`, y en memoria del proceso del backend hasta que se reinicia.

Para añadir otra química hace falta un modelo realmente disponible en PyBaMM, sus parámetros y una entrada en `backend/models/registry.py`. Litio, LFP, NMC y plomo aparecen en el selector como no implementados.

## Instalación

Hace falta Python 3.11 y Node.js 20.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
cd frontend
npm install
```

## Ejecución

En una terminal, desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python -m uvicorn backend.main:app --port 8000
```

En otra:

```powershell
cd frontend
npm run dev
```

La interfaz queda en `http://127.0.0.1:5173` y llama a `/api` en el puerto 8000.

## Pruebas

```powershell
.\.venv\Scripts\python -m pytest tests -q
```

Hay una descarga real de 30 s a 1 C. Comprueba que la simulación termina, que existen tiempo y voltaje, que las series tienen la misma longitud, que `Q = I·t/3600`, que el promedio inicial del electrolito es 1000 mol·m⁻³ y que cambiar el espesor del positivo mueve el voltaje. También comprueba que `Contact resistance [Ohm]` no lo mueve.

## Ejemplo

Descarga a 1 C (`3 mA` con la capacidad nominal de `3 mA·h`), 298.15 K, parámetros originales. El solver es `IDAKLUSolver`. El evento de voltaje mínimo corta cerca de 2540 s en 2.000 V, con un voltaje inicial de celda cercano a 3.821 V. Durante esa descarga PyBaMM puede avisar que el interpolante `k_n` se sale de su tabla. La interfaz muestra ese aviso.

La corriente positiva es descarga. El ciclo usa un único `solve` con un escalón de corriente, no `pybamm.Experiment`. El motivo está en las decisiones científicas.

## API

```text
GET  /api/health
GET  /api/models
GET  /api/models/{model}
GET  /api/models/{model}/parameters
GET  /api/models/{model}/variables
POST /api/parameters/validate
POST /api/simulate
POST /api/simulate/compare
GET  /api/configurations
POST /api/configurations
DELETE /api/configurations/{name}
```

`POST /api/simulate` recibe el modelo, solo los parámetros numéricos que cambiaron, el experimento y la lista de variables. La respuesta trae esas series y `Time [s]`. Un parámetro inválido o un fallo del solver responden con `error` y `details`, no con un 500 vacío.

La temperatura del experimento escribe `Initial temperature [K]`. La corriente escribe `Current function [A]`. Esas dos claves no se aceptan dentro de `parameters`.

## Estructura del resultado

Cada serie dice si salió directa del modelo o de un promedio de PyBaMM (`x_average`, y `r_average` cuando la variable vive en la partícula). Los campos espaciales completos no se envían.

## Dependencias

Backend: PyBaMM 26.9.0, FastAPI, Uvicorn, NumPy, SciPy, Pydantic. El solver viene con PyBaMM.

Frontend: React, TypeScript, Vite y Plotly.
