declare module "plotly.js-dist-min" {
  interface PlotlyStatic {
    newPlot(
      root: HTMLElement,
      data: object[],
      layout?: object,
      config?: object,
    ): Promise<void>;
    purge(root: HTMLElement): void;
  }
  const Plotly: PlotlyStatic;
  export default Plotly;
}
