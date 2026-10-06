import { useEffect, useRef } from "react";
import Plotly from "plotly.js-dist-min";
import type { RunRecord } from "./types";

const COLORS = ["#1f4e79", "#c45c26", "#2f6f4e", "#6b3fa0", "#8a6a2f", "#8f2d3c"];

type Props = {
  runs: RunRecord[];
  xKey: string;
  yKey: string;
};

export function ChartPanel({ runs, xKey, yKey }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const visible = runs.filter((run) => run.visible);
  const signature = JSON.stringify(
    visible.map((run) => [run.id, xKey, yKey, run.result.series[xKey]?.length, run.result.series[yKey]?.length]),
  );

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const traces = visible.flatMap((run, index) => {
      const x = run.result.series[xKey];
      const y = run.result.series[yKey];
      if (!x || !y) return [];
      return [
        {
          x,
          y,
          type: "scatter",
          mode: "lines",
          name: run.result.label,
          line: { color: COLORS[index % COLORS.length], width: 2 },
          hovertemplate: `${run.result.label}<br>${xKey}: %{x}<br>${yKey}: %{y}<extra></extra>`,
        },
      ];
    });
    Plotly.newPlot(
      element,
      traces,
      {
        margin: { t: 24, r: 16, b: 56, l: 64 },
        paper_bgcolor: "#f7f4ee",
        plot_bgcolor: "#fffdf8",
        xaxis: { title: { text: xKey }, gridcolor: "#e4ddd0" },
        yaxis: { title: { text: yKey }, gridcolor: "#e4ddd0" },
        legend: { orientation: "h", y: -0.25 },
        hovermode: "closest",
      },
      { responsive: true, scrollZoom: true, displaylogo: false },
    );
    return () => {
      Plotly.purge(element);
    };
  }, [signature]);

  return <div ref={ref} data-testid="chart" className="chart" />;
}
