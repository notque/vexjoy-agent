/**
 * ThresholdStep pairs a numeric lower boundary with a CSS color string.
 * Mirrors the #ThresholdStep CUE definition in the schema.
 */
export interface ThresholdStep {
  value: number;
  color: string;
}

/**
 * CustomPanelSpec is the validated configuration for a CustomPanel.
 * All fields mirror the CUE schema at schemas/panels/custom-panel/custom-panel.cue.
 */
export interface CustomPanelSpec {
  /** Display label rendered at the top of the panel. */
  title: string;
  /** Value formatting unit (e.g. "bytes", "percent", "ms", "short"). */
  unit?: string;
  /** Color-coded threshold steps. */
  thresholds?: ThresholdStep[];
}
