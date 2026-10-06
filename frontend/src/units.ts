import type { ParameterInfo } from "./types";

export function displayFactor(unit: string | null, mode: "si" | "um"): number {
  if (unit === "m" && mode === "um") return 1e6;
  return 1;
}

export function displayLabel(unit: string | null, mode: "si" | "um"): string {
  if (unit === "m" && mode === "um") return "µm";
  return unit ?? "adimensional";
}

export function formatShown(si: number, factor: number): string {
  const shown = si * factor;
  if (shown === 0) return "0";
  const abs = Math.abs(shown);
  if (abs >= 1e-4 && abs < 1e6) return String(Number(shown.toPrecision(8)));
  return shown.toExponential(4);
}

export function defaultDisplayMode(parameter: ParameterInfo): "si" | "um" {
  if (parameter.unit === "m" && parameter.original != null && Math.abs(parameter.original) < 1e-3) {
    return "um";
  }
  return "si";
}

export function constraintMessage(parameter: ParameterInfo, value: number): string | null {
  const rules: Array<["gt" | "ge" | "lt" | "le", string]> = [
    ["gt", "tiene que ser >"],
    ["ge", "tiene que ser ≥"],
    ["lt", "tiene que ser <"],
    ["le", "tiene que ser ≤"],
  ];
  for (const [key, text] of rules) {
    const limit = parameter.constraints[key];
    if (limit == null) continue;
    const ok =
      key === "gt" ? value > limit :
      key === "ge" ? value >= limit :
      key === "lt" ? value < limit :
      value <= limit;
    if (!ok) return `${text} ${limit} ${parameter.unit ?? ""}`.trim();
  }
  return null;
}
