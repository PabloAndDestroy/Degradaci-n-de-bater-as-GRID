# Parametrización y análisis numérico de baterías

Aplicación web para elegir un modelo de batería, ver y modificar sus parámetros, simular con [PyBaMM](https://github.com/pybamm-team/PyBaMM) y comparar las curvas. La primera química conectada es ion sodio.

PyBaMM sigue siendo el modelo físico y el solver. Esta aplicación no reimplementa el DFN ni copia el repositorio de PyBaMM dentro del proyecto.

Este README es la guía de traspaso. Léelo antes de tocar código. El detalle largo está en [docs/decisiones_cientificas.md](docs/decisiones_cientificas.md) y [docs/condiciones_de_simulacion.md](docs/condiciones_de_simulacion.md). Si el README y esos documentos se contradicen, manda el código y actualiza los tres.

## Qué hay en el modelo de sodio

Inspección de PyBaMM 26.9.0, fijada en `backend/requirements.txt`:

- El módulo `pybamm.sodium_ion` contiene una clase: `BasicDFN`.
- Es un Doyle–Fuller–Newman isotérmico. No trae opciones térmicas ni de degradación.
- El conjunto de parámetros por defecto es `Chayambuka2022` (hard carbon / NVPF / NaPF6 en EC:PC).
- Parte de los parámetros son números. OCP, difusividades, conductividad del electrolito y densidades de intercambio son funciones interpoladas. Las difusividades, la conductividad y las densidades de intercambio no se reemplazan por un número. El OCP sí puede reemplazarse por una tabla `ocp_tables`, no por un escalar.
- `BasicDFN` no calcula temperatura, SOC ni resistencia. Esos huecos están en la interfaz y en las decisiones científicas.

Fuentes upstream, que no se modifican:

- modelo: `packages/pybamm/src/pybamm/models/full_battery_models/sodium_ion`
- parámetros: `packages/pybamm/src/pybamm/input/parameters/sodium_ion`

## Mapa del código

```text
backend/main.py                      FastAPI, CORS, errores.
backend/api/routes.py                Rutas. SimulateIn acepta parameters, experiment y ocp_tables.
backend/models/registry.py           Solo sodium_ion está implementado. Litio, LFP, NMC y plomo están reservados.
backend/parameters/catalogue.py      Nombres, categorías y cotas leídas de ParameterValues("Chayambuka2022").
backend/parameters/presets.py        Agregados chayambuka y eafit.
backend/parameters/ocp_tables.py     Puntos canónicos EAFIT, validate_ocp_tables, ocp_interpolant.
backend/simulation/runner.py         prepare y simulate. Aplica overrides y, si hay tabla, el OCP.
backend/simulation/outputs.py        Series y promedios. Tope de 2000 puntos.
backend/validation/checks.py         Autoridad de validación. El frontend solo adelanta las mismas reglas.
frontend/src/App.tsx                 Selector de agregado, filas numéricas, editor de tablas OCP, gráfica.
frontend/src/types.ts                Contratos del cliente, incluido OcpTables.
tests/test_sodium_ion.py             Descarga real de 30 s y reglas del catálogo.
tests/test_presets.py                Contenido del agregado EAFIT.
tests/test_ocp_tables.py             Interpolante en los anclajes.
tests/test_ocp_api.py                La API rechaza tablas inválidas y un OCP escalar.
docs/decisiones_cientificas.md       Por qué el modelo se dejó como está publicado.
docs/condiciones_de_simulacion.md    Qué valida la app y qué no significa una simulación que termina.
```

No hay Docker, base de datos ni autenticación. Las configuraciones se guardan en un JSON descargado, en `localStorage` (clave `battery-configurations`) y en memoria del proceso del backend hasta que se reinicia.

## Features

1. Agregado de parámetros. El selector pide `GET /api/models/{model}/presets`.
   - `chayambuka`: parámetros publicados. No manda tablas OCP.
   - `eafit`: columna Celda EAFIT. Capacidad nominal 75 A·h, resistencia de contacto 0 Ω, temperaturas de referencia y ambiente 298.15 K, 1 electrodo en paralelo, 1 celda en serie, corte inferior 1.5 V, corte superior 3.9 V, experimento en modo corriente a 24.75 A y 298.15 K. «Restaurar parámetros» vuelve a Chayambuka y vacía las tablas.

2. Geometría y escalares de celda, ánodo y cátodo (espesor, altura, ancho, porosidad, fracción activa, radio, concentraciones, conductividad, Bruggeman) se editan en las filas numéricas. Esos números entran como overrides y el solver los usa. Los Excel de OCP no traen geometría. No se inventa ni se deduce de los 75 A·h. Cambiar la capacidad no reescala el área.

3. Curvas OCP editables. Al elegir EAFIT se cargan las tablas de `HC_OCP (U_n).xlsx` (ánodo, hard carbon) y `NFM_OCP (U_p).xlsx` (cátodo, NFM). La interfaz deja editar, agregar y quitar filas `(sto, V)`. La simulación las manda en `ocp_tables`, hermano de `parameters`. El runner las sustituye por un `pybamm.Interpolant` lineal en `Negative electrode OCP [V]` y `Positive electrode OCP [V]`. Sin tablas, o con listas vacías, sigue el OCP de Chayambuka. El positivo publicado es NVPF, no NFM. Un escalar no puede reemplazar esas funciones. Difusividad y densidad de intercambio no se sustituyen. Cada tabla, si viene, necesita al menos 2 puntos, `sto` estrictamente creciente y valores finitos. El positivo empieza en `sto = 0.17`; no se rellenan puntos por debajo de ese valor.

## Decisiones que no hay que reabrir

- Ecuaciones: `BasicDFN` coincide con el DFN de litio de Marquis et al. (2019). Cambian los parámetros, no las ecuaciones. No se copia ni se parchea el paquete.
- Materiales publicados: ánodo hard carbon, cátodo NVPF, electrolito NaPF6 en EC:PC (1:1). Cita: Chayambuka, Mulder, Danilov y Notten, *Electrochimica Acta* 404 (2022) 139764. Los números son los de la implementación COMSOL que referencia `Chayambuka2022.py`.
- Geometría publicada, no reescalada: espesor negativo 64 µm, separador 25 µm, positivo 68 µm; `Electrode height` 2.54×10⁻⁴ m; `Electrode width` 1 m; capacidad 3×10⁻³ A·h; corriente por defecto 3×10⁻³ A (1 C de esa capacidad).
- Estado que sí resuelve: concentración en partículas, concentración y potencial del electrolito, potencial de los sólidos, capacidad de descarga. Cinética Butler–Volmer. `dQ/dt = I/3600` con `Q` en A·h. En carga `I` es negativa y `Q` baja: la variable es *discharge capacity*.
- Temperatura: `Initial temperature [K]` es un dato. Entra en `F·η/(R·T)`. No hay ecuación térmica. No se grafica temperatura.
- Cortes de voltaje originales: 2.0 V y 4.2 V. Con EAFIT pasan a 1.5 V y 3.9 V solo si se aplica el agregado. El voltaje inicial no se impone: sale de concentraciones iniciales y OCP. Descarga de referencia a 1 C, 298.15 K: `V(0) ≈ 3.821 V`, corte en 2.000 V cerca de 2540 s. Ese tiempo no es 3 mA·h / 3 mA.
- Corriente positiva significa descarga. La interfaz pide magnitud; el tipo de experimento pone el signo. El ciclo es un solo `solve` con un escalón hecho con Heaviside, no `pybamm.Experiment`. En esta versión de PyBaMM un experimento descarga–reposo–carga saltaba de voltaje y descartaba la carga. Al invertir la corriente el voltaje salta (del orden de 0.33 V a 1 C) porque no hay capacitancia de doble capa.
- Una carga directa a 1 C con las concentraciones iniciales publicadas activa el corte superior antes de integrar. La API devuelve 422. No se fabrica un estado inicial de menor SOC.
- Promedios: se agregan al modelo antes de discretizar con `pybamm.x_average` y, en la partícula, `x_average(r_average(...))`. `r_average` es promedio en volumen, no la media de los nodos. Condición inicial: electrolito 1000 mol·m⁻³, partícula negativa 13520 mol·m⁻³. No se envían campos espaciales.
- Submuestreo: si hay más de 2000 instantes, la respuesta se queda con 2000 índices uniformes, primero y último incluidos. No es otra solución. El solver es `IDAKLUSolver`.
- Tope de 50 C y de 6 h: límite de la aplicación, no del solver. `I [A] = C-rate × capacidad nominal`. La corriente absoluta no puede pasar de `50 × capacidad nominal`.
- Cotas del catálogo (espesor > 0, porosidad en (0, 1), porosidad + fracción activa ≤ 1, concentración inicial ≤ máxima, cortes ordenados) son restricciones físicas. No son intervalos de calibración del artículo.
- Particularidad que no se corrige: en `Chayambuka2022.py` la difusividad del hard carbon interpola contra `sto` por la concentración máxima del negativo. La de NVPF interpola contra `sto` por `Initial concentration in electrolyte [mol.m-3]`. La variable local se llama `c_max` y no es la concentración máxima del positivo. Cambiarlo sería modificar el modelo publicado.
- Las funciones de electrolito reciben `T` y no la usan. Una temperatura distinta de 298.15 K entra por Butler–Volmer y, si se editó, por el término entrópico. El cambio entrópico publicado es 0. En una descarga a 1 C, `k_n` puede extrapolar por debajo de su tabla. El aviso se muestra. No se recorta la curva.

Parámetros que están en el conjunto y no hacen lo que el nombre sugiere en este `BasicDFN`:

| Parámetro | Efecto real |
| --- | --- |
| `Contact resistance [Ohm]` | Ninguno sobre `Voltage [V]`. No se resta `I·R`. |
| `Ambient temperature [K]` | Ninguno. No hay intercambio con el ambiente. |
| `Open-circuit voltage at 0% SOC [V]` y `at 100% SOC [V]` | Ninguno. No hay variable de SOC. |
| `Nominal cell capacity [A.h]` | No entra en los residuales. Solo convierte C-rate y arma el tope de 50 C. |
| `Reference temperature [K]` | Solo vía `(T − T_ref)·dU/dT`. Con dU/dT = 0 no mueve la solución. |
| Número de celdas en serie | Escala `Battery voltage [V]`, no `Voltage [V]`. |
| `Initial temperature [K]` | Sí mueve el voltaje, por la cinética, aunque dU/dT sea 0. |

No hay SEI, plating ni pérdida de material activo. No se calcula `V/I` ni una variable de degradación.

## De dónde salieron los números EAFIT

En la raíz hay dos Excel de comparación (el nombre en disco puede verse como `ParAmetros.xlsx` y `ParAmetros_hoja2.xlsx` por un mojibake de «Parámetros»). Son el mismo contenido. Solo se usó la hoja `Hoja2`, filas anteriores a «Datos adicionales del artículo respecto a la celda», columna **Celda EAFIT**.

Quedó fuera a propósito, y no hay que recuperarlo como si fuera la celda:

- desde «Datos adicionales» hacia abajo, incluidas sodificación y reactividades;
- la hoja `Art` (doble capa, colectores, calor, energías de activación);
- la columna sin encabezado al lado de Celda EAFIT (58.9 junto a 75, y 12 junto a 24.75);
- notas sueltas `1,97 nm`, `5,07 μm cat`, `4,32 μm anod`;
- las columnas Artículo Schneider y Artículo Schütte, y el bloque ánodo/cátodo de esa hoja, que no tiene columna EAFIT.

Esas celdas EAFIT estaban vacías: espesores, altura, ancho, porosidad y Bruggeman del separador, OCV a 0 % y a 100 % SOC. Siguen en los valores de Chayambuka hasta que alguien los escriba en las filas. 75 A·h y 24.75 A sobre el área publicada (altura 2.54×10⁻⁴ m por ancho 1 m) no son la densidad de corriente de una celda de 75 A·h a escala. La simulación puede no converger. No se reescala la geometría para disimularlo.

Los otros dos Excel, `HC_OCP (U_n).xlsx` y `NFM_OCP (U_p).xlsx`, solo traen sto contra voltaje. Esos puntos están copiados en `EAFIT_OCP_TABLES` dentro de `backend/parameters/ocp_tables.py`. El runtime no abre el Excel. Ánodo: sto 0 → 1.30 V y sto 1 → 0.03 V. Cátodo NFM: sto 0.17 → 3.95 V y sto 1 → 2.30 V. No son la curva NVPF de Chayambuka.

## Contrato que el código ya cumple

`ocp_tables` es hermano de `parameters`, no una clave dentro del mapa numérico:

```json
"ocp_tables": {
  "negative": [{"sto": 0.0, "V": 1.30}],
  "positive": [{"sto": 0.17, "V": 3.95}]
}
```

- Omitido, `null` o lista vacía: no sustituye ese electrodo.
- Tabla inválida: error de validación y no hay `solve`.
- `parameters["Negative electrode OCP [V]"]=3.5` sigue rechazado. Igual el positivo, y también `Current function [A]` e `Initial temperature [K]`, que los fija el experimento.

`prepare` fusiona overrides numéricos, escribe temperatura y corriente del experimento, y después, si hay puntos, hace `parameter_values.update` de las dos claves OCP con un callable `(sto) -> pybamm.Interpolant`.

## Qué no hacer en el siguiente cambio

- No inventar espesores, área, porosidad, difusividad ni densidad de intercambio que no estén en una fuente nombrada.
- No meter Schneider, Schütte ni «Datos adicionales» como si fueran la celda EAFIT.
- No reescalar la geometría de Chayambuka para que 75 A·h «quede coherente». Si llega geometría medida, se escribe como override explícito y se documenta la fuente.
- No sustituir difusividad, conductividad del electrolito ni exchange-current por un número o por una tabla nueva sin datos.
- No corregir el `c_max` de la difusividad NVPF.
- No añadir SEI, térmica, SOC ni resistencia `V/I` dentro de `BasicDFN`.
- No usar `pybamm.Experiment` para el ciclo mientras el salto de voltaje de esa vía siga como está descrito.
- Otra química (litio, LFP, NMC, plomo) solo entra si PyBaMM tiene el modelo y se registra en `backend/models/registry.py`.

## Instalación

Hace falta Python 3.11 y Node.js 20.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
cd frontend
npm install
```

## Ejecución

En una terminal, desde la raíz:

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
.\.venv\Scripts\python -m pytest tests -q -p no:cacheprovider
```

`test_sodium_ion.py` hace una descarga real de 30 s a 1 C. Comprueba que la simulación termina, que existen tiempo y voltaje, que las series tienen la misma longitud, que `Q = I·t/3600`, que el promedio inicial del electrolito es 1000 mol·m⁻³ y que cambiar el espesor del positivo mueve el voltaje. También comprueba que `Contact resistance [Ohm]` no lo mueve.

`test_ocp_tables.py` no lanza un DFN largo: evalúa el interpolante. `test_presets.py` y `test_ocp_api.py` cubren el agregado y el rechazo de tablas malas.

## Ejemplo

Descarga a 1 C (`3 mA` con la capacidad nominal de `3 mA·h`), 298.15 K, parámetros originales, sin `ocp_tables`. El solver es `IDAKLUSolver`. El evento de voltaje mínimo corta cerca de 2540 s en 2.000 V, con un voltaje inicial de celda cercano a 3.821 V. Durante esa descarga PyBaMM puede avisar que el interpolante `k_n` se sale de su tabla. La interfaz muestra ese aviso.

EAFIT no es ese ejemplo. Hay que elegir el agregado. La geometría sigue siendo la publicada hasta que se editen las filas.

## API

```text
GET  /api/health
GET  /api/models
GET  /api/models/{model}
GET  /api/models/{model}/parameters
GET  /api/models/{model}/presets
GET  /api/models/{model}/variables
POST /api/parameters/validate
POST /api/simulate
POST /api/simulate/compare
GET  /api/configurations
POST /api/configurations
DELETE /api/configurations/{name}
```

`POST /api/simulate` recibe el modelo, solo los parámetros numéricos que cambiaron, el experimento, la lista de variables y, si aplica, `ocp_tables`. La respuesta trae esas series y `Time [s]`. Un parámetro inválido o un fallo del solver responden con `error` y `details`, no con un 500 vacío. El 422 cubre tanto la validación como un fallo de IDAS.

La temperatura del experimento escribe `Initial temperature [K]`. La corriente escribe `Current function [A]`. Esas dos claves no se aceptan dentro de `parameters`.

`POST /api/simulate` y `POST /api/simulate/compare` aceptan `ocp_tables` opcional (`negative` y `positive`, listas de `{sto, V}`). También lo aceptan validate y las configuraciones guardadas.

## Estructura del resultado

Cada serie dice si salió directa del modelo o de un promedio de PyBaMM (`x_average`, y `r_average` cuando la variable vive en la partícula). Los campos espaciales completos no se envían.

## Dependencias

Backend: PyBaMM 26.9.0, FastAPI, Uvicorn, NumPy, SciPy, Pydantic. El solver viene con PyBaMM.

Frontend: React, TypeScript, Vite y Plotly.
