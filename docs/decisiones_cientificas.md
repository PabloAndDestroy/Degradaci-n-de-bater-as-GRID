# Decisiones científicas

PyBaMM 26.9.0. El modelo y los números salen del paquete instalado. Esta aplicación no copia el código de PyBaMM ni modifica sus ecuaciones.

## Modelo

Se usa `pybamm.sodium_ion.BasicDFN` con `pybamm.ParameterValues("Chayambuka2022")`.

`BasicDFN` es un Doyle–Fuller–Newman escrito en una sola clase. PyBaMM indica que las ecuaciones coinciden con las del DFN de litio y que cambian los parámetros. La cita de las ecuaciones en el código es Marquis et al. (2019). Los parámetros vienen de Chayambuka, Mulder, Danilov y Notten, *Electrochimica Acta* 404 (2022) 139764, con los valores numéricos de la implementación COMSOL que el propio archivo `Chayambuka2022.py` referencia.

Materiales de ese conjunto:

- ánodo de hard carbon;
- cátodo NVPF;
- electrolito NaPF6 en EC:PC (1:1).

Geometría publicada en el conjunto, no reescalada:

- espesor negativo 64 µm, separador 25 µm, positivo 68 µm;
- `Electrode height` 2.54×10⁻⁴ m y `Electrode width` 1 m;
- capacidad nominal 3×10⁻³ A·h;
- corriente por defecto 3×10⁻³ A, es decir 1 C si se usa esa capacidad.

## Qué resuelve BasicDFN

El estado incluye concentración en las partículas, concentración y potencial del electrolito, potencial de los sólidos y la capacidad de descarga. La cinética interfacial es Butler–Volmer. La temperatura que entra en `F·η/(R·T)` es el dato `Initial temperature [K]`, no una incógnita.

La capacidad obedece, dentro del modelo,

```text
dQ/dt = I / 3600
```

con `Q` en A·h e `I` en A. Con corriente constante, `Q(t) = I·t/3600`. La prueba automática comprueba esa relación. Durante la carga `I` es negativa y `Q` disminuye: la variable se llama *discharge capacity*, no capacidad acumulada absoluta.

Los eventos terminan la integración si el voltaje de celda baja de `Lower voltage cut-off [V]` (2.0 V) o supera `Upper voltage cut-off [V]` (4.2 V).

En una descarga a 1 C, 298.15 K y parámetros originales, esta versión de PyBaMM dio aproximadamente `V(0) = 3.821 V` y cortó en 2.000 V a `t ≈ 2540 s`. Ese tiempo no es la capacidad nominal partida por la corriente: el corte de voltaje llega antes de 3 mA·h. Es un resultado del modelo, no un ajuste de esta aplicación.

Una carga directa a 1 C con las concentraciones iniciales publicadas activa el evento de voltaje máximo antes de que empiece la integración. `BasicDFN` no busca automáticamente un estado de menor carga; para cargar, reduzca la corriente o use un ciclo descarga/carga, que empieza descargando. La API conserva el `422` de PyBaMM y explica esta condición, en vez de devolver una solución que viole el corte.

## Qué no resuelve, y cómo se muestra

Comprobado en el código de `BasicDFN` y, donde importa, con dos simulaciones de 30 s:

| Parámetro o variable | Efecto en este modelo |
| --- | --- |
| `Contact resistance [Ohm]` | Ninguno sobre `Voltage [V]`. El voltaje es el potencial del sólido positivo en el colector. No se resta `I·R` y no se inventa una resistencia. |
| `Ambient temperature [K]` | Ninguno. No hay ecuación térmica ni intercambio con el ambiente. |
| `Open-circuit voltage at 0% SOC [V]` y `at 100% SOC [V]` | Ninguno. No hay variable de SOC. |
| `Nominal cell capacity [A.h]` | Ninguno en los residuales. La aplicación sí lo usa para `I [A] = C-rate × capacidad [A.h]` y para calcular el límite de corriente de 50 C. |
| `Reference temperature [K]` | Solo a través de `(T − T_ref)·dU/dT`. Con el cambio entrópico publicado (0) no cambia la solución. |
| Cambio entrópico del OCP | El conjunto lo trae en 0. Si se edita, PyBaMM lo incorpora al OCP. Se comprobó que un valor distinto de cero mueve el voltaje. |
| `Initial temperature [K]` | Cambia el voltaje aunque el cambio entrópico sea cero, porque la cinética depende de `T`. |
| Número de celdas en serie | Cambia `Battery voltage [V]`. No cambia `Voltage [V]`. |

No hay SEI, plating ni pérdida de material activo. No se grafica temperatura: sería una recta constante y parecería una predicción térmica. No se calcula `V/I`.

El voltaje inicial no es una condición que el usuario pueda imponer. Sale de las concentraciones iniciales y de los OCP.

## Corriente

Convención de PyBaMM: corriente positiva, descarga. La interfaz pide una magnitud y el tipo de experimento pone el signo.

No se usa `pybamm.Experiment` para el ciclo. En esta versión, un experimento descarga–reposo–carga sobre `BasicDFN` saltó de 3.79 V al final de la descarga a 4.12 V al empezar el reposo, y PyBaMM descartó el paso de carga por considerarlo inviable en la condición inicial. Un solo `solve` con `Current function [A]` definida con funciones de Heaviside mantiene un único sistema. Al cambiar el signo de la corriente el voltaje también salta, del orden de 0.33 V a 1 C en el conjunto original. Ese salto es la desaparición instantánea de la polarización: `BasicDFN` no tiene capacitancia de doble capa.

## Promedios

Los campos espaciales se quedan en PyBaMM. La API solo devuelve series. Los promedios se agregan al modelo **antes** de discretizar:

- `pybamm.x_average` para campos a lo largo del espesor;
- `pybamm.x_average(pybamm.r_average(...))` para la concentración en la partícula.

`r_average` es el promedio en volumen de partícula de PyBaMM, no la media aritmética de los nodos. En la condición inicial uniforme, el promedio del electrolito vale 1000 mol·m⁻³ y el de la partícula negativa vale la concentración inicial (13520 mol·m⁻³). La prueba lo comprueba.

## Una particularidad que no se corrige

En `Chayambuka2022.py`, la difusividad del hard carbon interpola contra `sto` por la concentración máxima del electrodo negativo. La difusividad de NVPF interpola contra `sto` por `Initial concentration in electrolyte [mol.m-3]`. El nombre de la variable local es `c_max`, pero el parámetro no es la concentración máxima del positivo. Se deja así. Cambiarlo sería modificar el modelo publicado en esta versión de PyBaMM.

Las difusividades, OCP, conductividad del electrolito y densidades de intercambio son interpolantes. El artículo no da dependencia con la temperatura para el electrolito; las funciones reciben `T` y no la usan. Por eso una temperatura distinta de 298.15 K solo entra por Butler–Volmer y por el término entrópico.

En una descarga a 1 C, el solver avisa que el interpolante `k_n` extrapola por debajo de su tabla. El aviso se muestra tal cual. No se recorta la solución para esconderlo.

## Validación

Las cotas (espesor positivo, porosidad en (0, 1), porosidad + fracción activa ≤ 1, concentración inicial ≤ concentración máxima, cortes de voltaje ordenados) son restricciones físicas. No son intervalos de calibración del artículo: PyBaMM no los publica.

La capacidad nominal se puede cambiar desde las condiciones de simulación o desde el catálogo de parámetros. Sirve para convertir C-rate a corriente y para calcular el tope de corriente de 50 C de la aplicación. Por ejemplo, 6 A requieren una capacidad nominal de al menos 0.12 A·h para pasar esa validación. Cambiarla no reescala la geometría, las áreas de electrodo ni las ecuaciones de BasicDFN; para C-rate constante sí cambia la corriente que se aplica.

El tope de 50 C y de 6 h es de la aplicación, para no lanzar integraciones sin relación con las tablas. No es un límite del solver.

## Submuestreo

Si el solver devuelve más de 2000 instantes, la respuesta se queda con 2000 índices uniformes, incluyendo el primero y el último. No es una solución nueva. Las descargas de referencia de este modelo quedan por debajo de ese límite.
