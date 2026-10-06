# Condiciones y limitaciones de las simulaciones

Esta guía describe qué calcula la aplicación actualmente y bajo qué condiciones
puede ejecutarse una simulación. El backend usa **PyBaMM 26.9.0**, el modelo
**`pybamm.sodium_ion.BasicDFN`** y el conjunto de parámetros
**`Chayambuka2022`**. La validación de la aplicación evita algunas entradas
imposibles, pero no puede garantizar que todas las combinaciones restantes
converjan ni que sean representativas de una celda real.

Para la descripción del modelo y de las decisiones científicas, véase
[decisiones_cientificas.md](./decisiones_cientificas.md).

## Qué representa el modelo

- Es un modelo electroquímico DFN isotérmico para la celda de ion sodio del
  conjunto Chayambuka2022 (hard carbon / NVPF / NaPF6 en EC:PC).
- PyBaMM resuelve las concentraciones y potenciales definidos por `BasicDFN`.
  La temperatura es constante e impuesta por el experimento; no se resuelve un
  balance térmico.
- La capacidad nominal publicada es `0.003 A·h`. El conjunto publica la
  geometría y los materiales correspondientes a esa parametrización.
- Los eventos de voltaje interrumpen la integración cuando se alcanza el corte
  inferior o superior configurado. Con los parámetros originales son 2.0 V y
  4.2 V respectivamente.
- El voltaje inicial resulta de las concentraciones iniciales y los OCP; no es
  una condición inicial que esta interfaz permita imponer directamente.

Este modelo no predice por sí solo temperatura, SOC, resistencia interna,
degradación, SEI, plating ni pérdida de material activo. En particular,
`Contact resistance [Ohm]` no se resta del voltaje de `BasicDFN`.

## Condiciones que valida la aplicación

La API vuelve a validar los datos aunque ya se hayan validado visualmente en el
frontend. Los límites siguientes pertenecen a la aplicación; no deben
interpretarse como límites universales del hardware o de PyBaMM.

| Entrada | Condición aplicada |
| --- | --- |
| Tipo de experimento | `discharge`, `charge` o `cycle`. |
| Modo eléctrico | Corriente o C-rate. La magnitud debe ser finita y positiva; el tipo de experimento determina el signo. |
| C-rate | Mayor que 0 y como máximo 50 C. |
| Corriente | Mayor que 0 y como máximo `50 × capacidad nominal configurada` A. La corriente introducida es una magnitud, no lleva signo. |
| Temperatura | Finita y mayor que 0 K. Fuera de 250–350 K se agrega un aviso, no un rechazo automático. |
| Descarga o carga | Duración finita, mayor que 0 y no superior a 6 h. |
| Ciclo | Duraciones de descarga y carga finitas y mayores que 0; su suma no puede exceder 6 h. |
| Capacidad nominal | Finita y mayor que 0 A·h. |
| Porosidad y fracción activa | Cada fracción debe estar entre 0 y 1; por electrodo, porosidad + fracción activa no puede superar 1. |
| Concentraciones iniciales | Deben ser positivas y no superar la concentración máxima correspondiente del electrodo. |
| Cortes de voltaje | Ambos deben ser positivos y el corte inferior debe ser menor que el superior. |
| Otros parámetros numéricos | Se comprueba que el valor sea finito y se aplican las cotas de signo/unidad definidas en el catálogo. |

Las cotas físicas del catálogo no son intervalos de calibración publicados por
Chayambuka2022. Por ejemplo, que un espesor sea positivo no significa que
cualquier espesor positivo esté validado experimentalmente. La aplicación no
tiene todavía límites de incertidumbre o rangos de operación específicos del
fabricante.

## Capacidad nominal y corriente: una distinción importante

`Nominal cell capacity [A.h]` se puede modificar. En la aplicación se usa para:

1. Convertir una entrada en C-rate a corriente:
   `I [A] = C-rate × capacidad nominal [A·h]`.
2. Calcular el tope administrativo de corriente: `50 × capacidad nominal`.

Cambiarla **no** escala automáticamente espesores, áreas, volúmenes de
materiales activos, concentraciones, OCP ni la geometría de PyBaMM. Por tanto,
no convierte el modelo de la celda de 3 mA·h publicada en una celda física de
120 mA·h.

Ejemplo: establecer `0.12 A·h` hace que `6 A` pasen la comprobación
administrativa de 50 C. Sin embargo, 6 A equivalen a 2000 C respecto a la
capacidad publicada de 0.003 A·h. La condición pasa la validación de la
aplicación, pero no representa una simulación validada del modelo y puede hacer
que IDAS no encuentre una condición inicial consistente. Para representar una
batería de mayor capacidad hay que parametrizar coherentemente su geometría,
materiales, capacidad y condiciones iniciales; editar solo este número no es
suficiente.

Con los parámetros originales, 1 C equivale aproximadamente a 0.003 A. Incluso
a ese valor se pueden producir extrapolaciones de los interpolantes; el hecho
de que una simulación termine no elimina ese aviso.

## Casos límite de carga, descarga y ciclo

- **Corriente positiva significa descarga.** Para carga, la aplicación aplica
  corriente negativa automáticamente; no se debe introducir corriente negativa
  en el campo de magnitud.
- **Carga directa con las condiciones iniciales publicadas:** a 1 C, el voltaje
  inicial puede activar el evento de voltaje máximo antes de empezar la
  integración. En ese caso la API devuelve un `422`; no significa que la carga
  esté implementada como carga de una celda inicialmente descargada. `BasicDFN`
  no calcula el SOC ni busca automáticamente un estado inicial apropiado.
- **Ciclo:** se resuelve con un único `solve` y un escalón de corriente: primero
  descarga, luego carga. No incluye reposo, control por voltaje ni varias
  etapas. Al invertir instantáneamente la corriente puede observarse un salto
  de voltaje; el modelo no tiene capacitancia de doble capa que lo suavice.
- Una duración solicitada es un máximo. Si ocurre primero un evento de voltaje,
  PyBaMM termina antes y el tiempo final será menor.
- La aplicación no determina que una combinación de corriente, capacidad
  nominal, concentración inicial y parámetros de transporte sea operable en una
  celda real. La validación de entrada y la convergencia del solver son cosas
  distintas.

## Parámetros que no se pueden modificar o que no conviene interpretar como controles físicos

### No editables en esta interfaz

- Los parámetros que PyBaMM entrega como funciones (OCP, difusividades,
  conductividad del electrolito y densidades de intercambio) no aceptan ser
  sustituidos por un escalar. Modificar esas curvas requiere una función
  compatible con PyBaMM, los dominios y unidades correctos, y datos que la
  respalden.
- `Current function [A]` e `Initial temperature [K]` son controlados por las
  condiciones del experimento. El backend rechaza sobrescribirlos también
  dentro del mapa `parameters`.

### Editables, pero sin el efecto que su nombre podría sugerir

| Parámetro | Limitación |
| --- | --- |
| `Nominal cell capacity [A.h]` | Solo se usa para convertir C-rate y validar la corriente. No escala el modelo físico. |
| `Contact resistance [Ohm]` | No afecta `Voltage [V]` en `BasicDFN`; no se calcula ni se resta una caída `I·R`. |
| `Ambient temperature [K]` | No existe ecuación térmica ni intercambio con el ambiente; la temperatura del modelo la fija el experimento. |
| `Open-circuit voltage at 0% SOC [V]` y `Open-circuit voltage at 100% SOC [V]` | No entran en las ecuaciones ni en los eventos de voltaje de este `BasicDFN`; el modelo no tiene una variable SOC. |
| `Reference temperature [K]` | Solo importa a través del término entrópico del OCP. Con el cambio entrópico original, que es 0, variar esta referencia no produce efecto. |
| `Number of cells connected in series to make a battery` | Escala `Battery voltage [V]`, no el voltaje de celda `Voltage [V]`. |

La interfaz marca los parámetros que no afectan el DFN. No conviene cambiar un
parámetro sin efecto esperando modificar la simulación; tampoco conviene
presentar como predicción una variable que el modelo no calcula.

### Parámetros acoplados

Al cambiar un parámetro de material, geometría o condición inicial, revisa sus
dependencias. Algunos ejemplos:

- Cambiar porosidad o fracción de material activo debe mantener
  `porosidad + fracción activa ≤ 1` en cada electrodo.
- Cambiar la concentración máxima puede hacer inválida la concentración
  inicial del electrodo correspondiente.
- Cambiar espesores, radios de partículas, fracciones activas o transporte puede
  cambiar escalas de tiempo, polarización y convergencia del solver. No se
  recomienda tratar esos cambios como independientes si se está representando
  otra celda.
- Un parámetro numérico editable no necesariamente tiene un rango
  experimentalmente validado; la comprobación de signo es una guarda mínima,
  no una calibración.

## Interpolantes y avisos

Algunas propiedades son tablas interpoladas y tienen dominios de datos finitos.
Si el estado de la simulación sale de una tabla, PyBaMM puede emitir una
advertencia de extrapolación; por ejemplo, durante la descarga de referencia a
1 C puede extrapolar el interpolante `k_n`. La aplicación conserva el aviso en
los resultados. No recorta ni ajusta la curva para ocultarlo.

Una advertencia de extrapolación indica que se está usando la función fuera de
su tabla de datos, no necesariamente que el solver haya fallado. Aun cuando el
solver termine, las predicciones en esa región requieren cautela.

## Errores del solver

El backend devuelve `422` tanto para entradas rechazadas como para una
simulación que PyBaMM/IDAS no logra resolver, con mensaje y detalles. Algunos
casos posibles:

- `Maximum voltage [V] ... non-positive at initial conditions`: el evento de
  voltaje máximo ya está activo en el estado inicial, frecuente en una carga
  directa con parámetros iniciales originales.
- `IDAGetDky: IDA_BAD_K` puede ser un error secundario. Si IDAS falla antes al
  construir la condición inicial o al converger el corrector, no tiene una
  solución válida de la que calcular la derivada solicitada. No se corrige
  cambiando la duración de la gráfica; hay que revisar corriente, condiciones
  iniciales y coherencia de parámetros.
- Corriente elevada respecto a los parámetros físicos puede causar un fallo de
  convergencia aunque la corriente pase el límite administrativo de 50 C.

Reducir la corriente puede ser útil para diagnosticar; no convierte por sí solo
una parametrización ajena al conjunto en un modelo validado. Si el fallo
persiste con los parámetros originales y una corriente moderada, conserva el
mensaje completo del solver, los parámetros modificados, el tipo de experimento
y las duraciones para reproducirlo.

## Variables y resolución de resultados

- Solo se devuelven variables que `BasicDFN` expone y que pueden representarse
  como series temporales. Los campos espaciales completos no se envían; para
  ciertas variables hay promedios de PyBaMM sobre el espesor o sobre la
  partícula.
- Temperatura, SOC, resistencia y degradación aparecen como no disponibles;
  no son variables resueltas por este modelo.
- Si el solver produce más de 2000 instantes, la respuesta se submuestrea a
  2000 puntos incluyendo los extremos. El submuestreo es solo para el resultado
  enviado y no vuelve a resolver ni modifica la solución de PyBaMM.

## Alcance de los resultados

La aplicación sirve para explorar el `BasicDFN` y el conjunto de parámetros
incluido, no para certificar una batería, estimar seguridad, predecir
temperaturas, vida útil o degradación, ni extrapolar sin validación a otra
química o formato de celda. Para estudiar esas propiedades hace falta un modelo
con las ecuaciones y datos correspondientes, y validar sus resultados contra
mediciones.
