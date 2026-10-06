export type ModelInfo = {
  id: string;
  name: string;
  implemented: boolean;
  notes?: string[];
  parameter_set?: string;
  model_class?: string;
  thermal?: string;
  equations?: string;
};

export type ParameterInfo = {
  name: string;
  unit: string | null;
  category: string;
  type: "number" | "function" | "other";
  editable: boolean;
  affects_basic_dfn: boolean;
  original: number | null;
  constraints: Partial<Record<"gt" | "ge" | "lt" | "le", number>>;
  description: string;
  function_summary: string | null;
};

export type ParameterResponse = {
  model: string;
  parameter_set: string;
  categories: string[];
  citations: string[];
  parameters: ParameterInfo[];
};

export type VariableInfo = {
  name: string;
  plottable: boolean;
  reason: string | null;
  source: string;
  description?: string;
};

export type ExperimentType = "discharge" | "charge" | "cycle";

export type ExperimentInput = {
  type: ExperimentType;
  current_mode: "current" | "c_rate";
  current_A: number | null;
  c_rate: number | null;
  duration_s: number | null;
  discharge_duration_s: number | null;
  charge_duration_s: number | null;
  temperature_K: number;
};

export type SimulateRequest = {
  model: string;
  label: string;
  parameters: Record<string, number>;
  experiment: ExperimentInput;
  variables: string[];
};

export type SimulationResult = {
  label: string;
  model: string;
  parameter_set: string;
  solver: string;
  termination: string;
  warnings: string[];
  elapsed_s: number;
  n_solver_points: number;
  n_points: number;
  downsampled: boolean;
  applied: {
    type: string;
    current_magnitude_A: number;
    temperature_K: number;
    duration_requested_s: number;
    t_end_s: number;
    sign_convention: string;
  };
  series: Record<string, number[]>;
  series_meta: Record<string, { unit: string | null; source: string; description: string }>;
};

export type SavedConfiguration = {
  name: string;
  model: string;
  parameters: Record<string, number>;
  experiment: ExperimentInput;
};

export type RunRecord = {
  id: string;
  request: SimulateRequest;
  result: SimulationResult;
  visible: boolean;
};
