import { useEffect, useMemo, useState } from "react";
import { ApiError, getJson, postJson } from "./api";
import { ChartPanel } from "./ChartPanel";
import type {
  ExperimentInput,
  ExperimentType,
  ModelInfo,
  ParameterInfo,
  ParameterResponse,
  RunRecord,
  SavedConfiguration,
  SimulationResult,
  SimulateRequest,
  VariableInfo,
} from "./types";
import { constraintMessage, defaultDisplayMode, displayFactor, displayLabel, formatShown } from "./units";

const STORAGE_KEY = "battery-configurations";
const NOMINAL_CAPACITY_PARAMETER = "Nominal cell capacity [A.h]";
const PRESETS: Array<[string, string, string]> = [
  ["Voltaje vs tiempo", "Time [s]", "Voltage [V]"],
  ["Voltaje vs capacidad", "Discharge capacity [A.h]", "Voltage [V]"],
  ["Corriente vs tiempo", "Time [s]", "Current [A]"],
  ["Capacidad vs tiempo", "Time [s]", "Discharge capacity [A.h]"],
];

const emptyExperiment = (): ExperimentInput => ({
  type: "discharge",
  current_mode: "c_rate",
  current_A: 0.003,
  c_rate: 1,
  duration_s: 3600,
  discharge_duration_s: 1800,
  charge_duration_s: 1800,
  temperature_K: 298.15,
});

function loadSaved(): SavedConfiguration[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as SavedConfiguration[]) : [];
  } catch {
    return [];
  }
}

function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    return [error.message, ...error.details].join("\n");
  }
  return error instanceof Error ? error.message : String(error);
}

export default function App() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [modelId, setModelId] = useState("sodium_ion");
  const [catalogue, setCatalogue] = useState<ParameterResponse | null>(null);
  const [variables, setVariables] = useState<VariableInfo[]>([]);
  const [unavailable, setUnavailable] = useState<Array<{ name: string; reason: string }>>([]);
  const [selectedVariables, setSelectedVariables] = useState<string[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [displayMode, setDisplayMode] = useState<Record<string, "si" | "um">>({});
  const [experiment, setExperiment] = useState<ExperimentInput>(emptyExperiment);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [xKey, setXKey] = useState("Time [s]");
  const [yKey, setYKey] = useState("Voltage [V]");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [configName, setConfigName] = useState("descarga de referencia");
  const [saved, setSaved] = useState<SavedConfiguration[]>(loadSaved);
  const [pybammVersion, setPybammVersion] = useState("");

  useEffect(() => {
    getJson<{ models: ModelInfo[] }>("/api/models").then((data) => setModels(data.models)).catch((reason) => setError(errorText(reason)));
    getJson<{ pybamm: string }>("/api/health").then((data) => setPybammVersion(data.pybamm)).catch(() => setPybammVersion(""));
  }, []);

  useEffect(() => {
    const selected = models.find((model) => model.id === modelId);
    if (!selected?.implemented) return;
    setDrafts({});
    setError("");
    Promise.all([
      getJson<ParameterResponse>(`/api/models/${modelId}/parameters`),
      getJson<{ variables: VariableInfo[]; not_available: Array<{ name: string; reason: string }> }>(
        `/api/models/${modelId}/variables`,
      ),
    ])
      .then(([parameters, variablePayload]) => {
        setCatalogue(parameters);
        setVariables(variablePayload.variables);
        setUnavailable(variablePayload.not_available);
        const plottable = variablePayload.variables.filter((item) => item.plottable && item.name !== "Time [s]");
        setSelectedVariables(plottable.map((item) => item.name));
        const modes: Record<string, "si" | "um"> = {};
        for (const parameter of parameters.parameters) modes[parameter.name] = defaultDisplayMode(parameter);
        setDisplayMode(modes);
      })
      .catch((reason) => setError(errorText(reason)));
  }, [modelId, models]);

  const parameters = catalogue?.parameters ?? [];
  const byName = useMemo(() => new Map(parameters.map((parameter) => [parameter.name, parameter])), [parameters]);

  function siValue(parameter: ParameterInfo): number | null {
    const raw = drafts[parameter.name];
    if (raw == null || raw.trim() === "") return parameter.original;
    const value = Number(raw);
    return Number.isFinite(value) ? value : null;
  }

  function overrides(): Record<string, number> {
    const values: Record<string, number> = {};
    for (const parameter of parameters) {
      if (!parameter.editable || parameter.original == null) continue;
      const value = siValue(parameter);
      if (value == null || !materiallyDifferent(value, parameter.original)) continue;
      values[parameter.name] = value;
    }
    return values;
  }

  function localErrors(): string[] {
    const messages: string[] = [];
    for (const parameter of parameters) {
      const raw = drafts[parameter.name];
      if (raw == null) continue;
      const value = Number(raw);
      if (!Number.isFinite(value)) {
        messages.push(`${parameter.name}: número no válido.`);
        continue;
      }
      const message = constraintMessage(parameter, value);
      if (message) messages.push(`${parameter.name}: ${message}.`);
    }
    if (!(experiment.temperature_K > 0)) messages.push("La temperatura tiene que ser > 0 K.");
    return messages;
  }

  function buildRequest(label: string): SimulateRequest {
    return {
      model: modelId,
      label,
      parameters: overrides(),
      experiment,
      variables: selectedVariables,
    };
  }

  async function runRequest(request: SimulateRequest) {
    const result = await postJson<SimulationResult>("/api/simulate", request);
    setRuns((current) => [
      ...current,
      { id: crypto.randomUUID(), request, result, visible: true },
    ]);
  }

  async function onRun() {
    const messages = localErrors();
    if (messages.length) {
      setError(messages.join("\n"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      const label = `Simulación ${runs.length + 1}`;
      await runRequest(buildRequest(label));
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function onCompare() {
    const previous = runs[runs.length - 1];
    if (!previous) return;
    const messages = localErrors();
    if (messages.length) {
      setError(messages.join("\n"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      const current = buildRequest("Configuración actual");
      const payload = {
        cases: [
          { ...previous.request, label: `${previous.result.label} (recalculada)`, variables: selectedVariables },
          current,
        ],
      };
      const response = await postJson<{ cases: SimulationResult[] }>("/api/simulate/compare", payload);
      setRuns((existing) => [
        ...existing.map((run) => ({ ...run, visible: false })),
        ...response.cases.map((result, index) => ({
          id: crypto.randomUUID(),
          request: index === 0 ? previous.request : current,
          result,
          visible: true,
        })),
      ]);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  function persist(next: SavedConfiguration[]) {
    setSaved(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  function currentConfiguration(name: string): SavedConfiguration {
    return { name, model: modelId, parameters: overrides(), experiment };
  }

  async function onSave() {
    const configuration = currentConfiguration(configName.trim() || "sin nombre");
    persist([configuration, ...saved.filter((item) => item.name !== configuration.name)]);
    const blob = new Blob([JSON.stringify(configuration, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${configuration.name}.json`;
    link.click();
    URL.revokeObjectURL(url);
    try {
      await postJson("/api/configurations", configuration);
    } catch (reason) {
      setError(errorText(reason));
    }
  }

  function applyConfiguration(configuration: SavedConfiguration) {
    if (configuration.model !== modelId) {
      setError("Esa configuración pertenece a otro modelo.");
      return;
    }
    const next: Record<string, string> = {};
    for (const [name, value] of Object.entries(configuration.parameters)) {
      next[name] = String(value);
    }
    setDrafts(next);
    setExperiment(configuration.experiment);
    setError("");
  }

  const nominal = byName.get(NOMINAL_CAPACITY_PARAMETER);
  const nominalValue = nominal ? siValue(nominal) : null;
  const magnitude =
    experiment.current_mode === "c_rate"
      ? (experiment.c_rate ?? 0) * (nominalValue ?? 0)
      : experiment.current_A ?? 0;
  const signedCurrent = experiment.type === "charge" ? -magnitude : magnitude;
  const axisOptions = axisKeys(runs.filter((run) => run.visible));
  const activeModel = models.find((model) => model.id === modelId);

  return (
    <main>
      <header>
        <h1>Parametrización de baterías</h1>
        <p>
          Sodium-ion con PyBaMM {pybammVersion || ""} · BasicDFN · conjunto Chayambuka2022.
          La corriente positiva es descarga.
        </p>
      </header>

      <div className="layout">
        <section className="panel">
          <h2>Modelo y parámetros</h2>
          <label className="field">
            Tipo de batería
            <select
              data-testid="model-select"
              value={modelId}
              onChange={(event) => {
                const next = models.find((model) => model.id === event.target.value);
                if (next && !next.implemented) return;
                setModelId(event.target.value);
              }}
            >
              {models.map((model) => (
                <option key={model.id} value={model.id} disabled={!model.implemented}>
                  {model.name}{model.implemented ? "" : " (no implementado)"}
                </option>
              ))}
            </select>
          </label>
          {activeModel?.notes && (
            <ul className="notes">
              {activeModel.notes.map((note) => <li key={note}>{note}</li>)}
            </ul>
          )}
          <label className="field">
            Buscar
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="espesor, porosidad, OCP…" />
          </label>
          <div className="toolbar">
            <button
              className="secondary"
              type="button"
              onClick={() => {
                setDrafts({});
                setExperiment((current) => ({ ...current, temperature_K: 298.15 }));
              }}
            >
              Restaurar parámetros
            </button>
          </div>
          {(catalogue?.categories ?? []).map((category) => {
            const rows = parameters.filter((parameter) => {
              if (parameter.category !== category) return false;
              const haystack = `${parameter.name} ${parameter.description}`.toLowerCase();
              return haystack.includes(query.trim().toLowerCase());
            });
            if (!rows.length) return null;
            return (
              <details key={category} open>
                <summary>{category}</summary>
                {rows.map((parameter) => (
                  <ParameterRow
                    key={parameter.name}
                    parameter={parameter}
                    mode={displayMode[parameter.name] ?? "si"}
                    raw={drafts[parameter.name]}
                    readOnlyValue={
                      parameter.name === "Initial temperature [K]"
                        ? experiment.temperature_K
                        : parameter.name === "Current function [A]"
                          ? signedCurrent
                          : null
                    }
                    onMode={(mode) => setDisplayMode((current) => ({ ...current, [parameter.name]: mode }))}
                    onDraft={(value) => setDrafts((current) => ({ ...current, [parameter.name]: value }))}
                    onReset={() =>
                      setDrafts((current) => {
                        const next = { ...current };
                        delete next[parameter.name];
                        return next;
                      })
                    }
                  />
                ))}
              </details>
            );
          })}
        </section>

        <div className="stack">
          <section className="panel">
            <h2>Condiciones de simulación</h2>
            <div className="row">
              <label className="field">
                Experimento
                <select
                  data-testid="experiment-type"
                  value={experiment.type}
                  onChange={(event) =>
                    setExperiment({ ...experiment, type: event.target.value as ExperimentType })
                  }
                >
                  <option value="discharge">Descarga a corriente constante</option>
                  <option value="charge">Carga a corriente constante</option>
                  <option value="cycle">Ciclo descarga / carga</option>
                </select>
              </label>
              <label className="field">
                Entrada eléctrica
                <select
                  value={experiment.current_mode}
                  onChange={(event) =>
                    setExperiment({
                      ...experiment,
                      current_mode: event.target.value as ExperimentInput["current_mode"],
                    })
                  }
                >
                  <option value="c_rate">C-rate</option>
                  <option value="current">Corriente (A)</option>
                </select>
              </label>
            </div>
            <div className="row">
              {experiment.current_mode === "c_rate" ? (
                <label className="field">
                  C-rate
                  <input
                    data-testid="c-rate"
                    type="number"
                    step="any"
                    value={experiment.c_rate ?? ""}
                    onChange={(event) =>
                      setExperiment({ ...experiment, c_rate: Number(event.target.value) })
                    }
                  />
                </label>
              ) : (
                <label className="field">
                  Magnitud de corriente (A)
                  <input
                    data-testid="current-a"
                    type="number"
                    step="any"
                    min="0"
                    value={experiment.current_A ?? ""}
                    onChange={(event) =>
                      setExperiment({ ...experiment, current_A: Number(event.target.value) })
                    }
                  />
                </label>
              )}
              <label className="field">
                Temperatura isotérmica (K)
                <input
                  data-testid="temperature"
                  type="number"
                  step="any"
                  value={experiment.temperature_K}
                  onChange={(event) =>
                    setExperiment({ ...experiment, temperature_K: Number(event.target.value) })
                  }
                />
              </label>
            </div>
            {experiment.type === "cycle" ? (
              <div className="row">
                <label className="field">
                  Descarga (s)
                  <input
                    type="number"
                    step="any"
                    value={experiment.discharge_duration_s ?? ""}
                    onChange={(event) =>
                      setExperiment({ ...experiment, discharge_duration_s: Number(event.target.value) })
                    }
                  />
                </label>
                <label className="field">
                  Carga (s)
                  <input
                    type="number"
                    step="any"
                    value={experiment.charge_duration_s ?? ""}
                    onChange={(event) =>
                      setExperiment({ ...experiment, charge_duration_s: Number(event.target.value) })
                    }
                  />
                </label>
              </div>
            ) : (
              <label className="field">
                Duración solicitada (s)
                <input
                  data-testid="duration"
                  type="number"
                  step="any"
                  value={experiment.duration_s ?? ""}
                  onChange={(event) =>
                    setExperiment({ ...experiment, duration_s: Number(event.target.value) })
                  }
                />
              </label>
            )}
            <p className="meta">
              Corriente aplicada: {signedCurrent.toExponential(4)} A.
              {experiment.type === "charge" ? " El signo negativo lo pone la carga." : ""}
              {experiment.type === "cycle"
                ? " En el ciclo, la corriente cambia de signo con un escalón. BasicDFN no tiene capacitancia de doble capa, así que el voltaje salta al cambiar la corriente."
                : ""}
              {" "}El voltaje inicial no es un dato: sale de las concentraciones iniciales y del OCP.
            </p>
            <div className="toolbar">
              <button data-testid="run" type="button" disabled={busy} onClick={onRun}>
                {busy ? "Resolviendo…" : "Ejecutar simulación"}
              </button>
              <button type="button" className="secondary" disabled={busy || runs.length === 0} onClick={onCompare}>
                Comparar con la anterior
              </button>
            </div>
          </section>

          <section className="panel">
            <h2>Resultados</h2>
            <div className="toolbar">
              {PRESETS.map(([label, x, y]) => (
                <button key={label} className="secondary" type="button" onClick={() => { setXKey(x); setYKey(y); }}>
                  {label}
                </button>
              ))}
            </div>
            <div className="row">
              <label className="field">
                Eje X
                <select data-testid="axis-x" value={xKey} onChange={(event) => setXKey(event.target.value)}>
                  {axisOptions.map((name) => <option key={name}>{name}</option>)}
                </select>
              </label>
              <label className="field">
                Eje Y
                <select data-testid="axis-y" value={yKey} onChange={(event) => setYKey(event.target.value)}>
                  {axisOptions.map((name) => <option key={name}>{name}</option>)}
                </select>
              </label>
            </div>
            <div className="runs">
              {runs.map((run) => (
                <label key={run.id} className="run-chip">
                  <input
                    type="checkbox"
                    checked={run.visible}
                    onChange={() =>
                      setRuns((current) =>
                        current.map((item) => item.id === run.id ? { ...item, visible: !item.visible } : item),
                      )
                    }
                  />
                  {run.result.label}
                </label>
              ))}
            </div>
            {runs.some((run) => run.visible) ? (
              <ChartPanel runs={runs} xKey={xKey} yKey={yKey} />
            ) : (
              <p data-testid="chart-empty">Ejecuta una simulación para ver la curva.</p>
            )}
            {runs.filter((run) => run.visible).map((run) => (
              <p key={run.id} className="meta">
                {run.result.label}: {run.result.termination}. t = {run.result.applied.t_end_s.toFixed(2)} s
                de {run.result.applied.duration_requested_s} s pedidos.
                Solver {run.result.solver}, {run.result.elapsed_s.toFixed(2)} s de cálculo,
                {run.result.n_points} puntos{run.result.downsampled ? " (submuestreados)" : ""}.
                {run.result.warnings.length ? ` Avisos: ${run.result.warnings.join(" ")}` : ""}
              </p>
            ))}
            <details>
              <summary>Variables que este modelo no calcula</summary>
              <ul className="notes">
                {unavailable.map((item) => <li key={item.name}><strong>{item.name}.</strong> {item.reason}</li>)}
              </ul>
            </details>
            <details>
              <summary>Variables de la próxima simulación</summary>
              {variables.filter((item) => item.plottable && item.name !== "Time [s]").map((item) => (
                <label key={item.name} className="run-chip">
                  <input
                    type="checkbox"
                    checked={selectedVariables.includes(item.name)}
                    onChange={() =>
                      setSelectedVariables((current) =>
                        current.includes(item.name)
                          ? current.filter((name) => name !== item.name)
                          : [...current, item.name],
                      )
                    }
                  />
                  {item.name}
                  {item.source === "reduction" ? " · promedio PyBaMM" : ""}
                </label>
              ))}
            </details>
          </section>

          <section className="panel">
            <h2>Configuraciones</h2>
            <div className="row">
              <label className="field">
                Nombre
                <input value={configName} onChange={(event) => setConfigName(event.target.value)} />
              </label>
              <div className="toolbar" style={{ alignItems: "end" }}>
                <button type="button" className="secondary" onClick={onSave}>Guardar JSON</button>
                <label className="field">
                  Cargar JSON
                  <input
                    type="file"
                    accept="application/json"
                    onChange={async (event) => {
                      const file = event.target.files?.[0];
                      if (!file) return;
                      try {
                        applyConfiguration(JSON.parse(await file.text()) as SavedConfiguration);
                      } catch (reason) {
                        setError(errorText(reason));
                      }
                    }}
                  />
                </label>
              </div>
            </div>
            <div className="toolbar">
              {saved.map((configuration) => (
                <button
                  key={configuration.name}
                  type="button"
                  className="secondary"
                  onClick={() => applyConfiguration(configuration)}
                >
                  {configuration.name}
                </button>
              )              )}
            </div>
            {nominal && (
              <label className="field">
                Capacidad nominal de la batería (A·h)
                <input
                  data-testid="nominal-capacity"
                  aria-label="Capacidad nominal de la batería (A·h)"
                  type="number"
                  step="any"
                  min="0"
                  value={drafts[NOMINAL_CAPACITY_PARAMETER] ?? String(nominal.original ?? "")}
                  onChange={(event) =>
                    setDrafts((current) => ({
                      ...current,
                      [NOMINAL_CAPACITY_PARAMETER]: event.target.value,
                    }))
                  }
                />
                <span className="meta">
                  Se usa para convertir C-rate a amperios y para el límite de corriente (50 C).
                  No cambia por sí sola la geometría ni las ecuaciones del DFN.
                </span>
              </label>
            )}
            <p className="meta">
              El archivo JSON y el almacenamiento del navegador conservan la configuración.
              El servidor solo la guarda en memoria hasta que se reinicia.
            </p>
          </section>
          {error && <pre className="error" data-testid="error">{error}</pre>}
        </div>
      </div>
    </main>
  );
}

function materiallyDifferent(value: number, original: number): boolean {
  return Math.abs(value - original) > 1e-12 * Math.max(1, Math.abs(original));
}

function axisKeys(runs: RunRecord[]): string[] {
  const present = new Set<string>(["Time [s]", "Voltage [V]", "Current [A]", "Discharge capacity [A.h]"]);
  for (const run of runs) {
    for (const name of Object.keys(run.result.series)) present.add(name);
  }
  return [...present];
}

function ParameterRow({
  parameter,
  mode,
  raw,
  readOnlyValue,
  onMode,
  onDraft,
  onReset,
}: {
  parameter: ParameterInfo;
  mode: "si" | "um";
  raw: string | undefined;
  readOnlyValue: number | null;
  onMode: (mode: "si" | "um") => void;
  onDraft: (value: string) => void;
  onReset: () => void;
}) {
  const factor = displayFactor(parameter.unit, mode);
  const si = raw != null && raw.trim() !== "" ? Number(raw) : parameter.original;
  const shown = readOnlyValue != null ? readOnlyValue * factor : si == null || !Number.isFinite(si) ? "" : formatShown(si / factor, 1);
  const edited =
    parameter.original != null &&
    raw != null &&
    raw.trim() !== "" &&
    Number.isFinite(Number(raw)) &&
    Math.abs(Number(raw) - parameter.original) > 1e-12 * Math.max(1, Math.abs(parameter.original));
  const message =
    parameter.editable && raw != null
      ? !Number.isFinite(Number(raw))
        ? "Número no válido."
        : constraintMessage(parameter, Number(raw))
      : null;

  return (
    <article className="parameter" data-testid={`param-${parameter.name}`}>
      <header>
        <h3>{parameter.name}</h3>
        <span className="meta">{parameter.affects_basic_dfn ? "entra en BasicDFN" : "no cambia el DFN"}</span>
      </header>
      {parameter.type === "function" ? (
        <p className="meta">{parameter.function_summary}</p>
      ) : (
        <>
          <div className="controls">
            <input
              aria-label={parameter.name}
              disabled={!parameter.editable}
              type="number"
              step="any"
              value={
                parameter.editable
                  ? raw == null || raw.trim() === "" || !Number.isFinite(Number(raw))
                    ? parameter.original == null
                      ? ""
                      : formatShown(parameter.original, factor)
                    : formatShown(Number(raw), factor)
                  : shown
              }
              onChange={(event) => {
                if (event.target.value.trim() === "") {
                  onDraft("");
                  return;
                }
                const entered = Number(event.target.value);
                if (!Number.isFinite(entered)) return;
                onDraft(String(entered / factor));
              }}
            />
            {parameter.unit === "m" ? (
              <select aria-label={`unidad ${parameter.name}`} value={mode} onChange={(event) => onMode(event.target.value as "si" | "um")}>
                <option value="um">µm</option>
                <option value="si">m</option>
              </select>
            ) : (
              <span className="meta">{displayLabel(parameter.unit, mode)}</span>
            )}
            {parameter.editable ? (
              <button type="button" className="secondary" onClick={onReset} disabled={!edited}>
                Restaurar
              </button>
            ) : <span />}
          </div>
          {parameter.original != null && (
            <p className="meta">
              Original: {formatShown(parameter.original, factor)} {displayLabel(parameter.unit, mode)}
              {edited && Number.isFinite(Number(raw)) ? ` · modificado: ${formatShown(Number(raw), factor)}` : ""}
            </p>
          )}
        </>
      )}
      {parameter.description && <p className="meta">{parameter.description}</p>}
      {message && <p className="warn">{message}</p>}
    </article>
  );
}
