/**
 * ExamplePanelSpec mirrors the CUE schema at
 * schemas/panels/example-panel/spec.cue.
 *
 * Field names and optionality MUST stay in sync with the CUE definition.
 */
export interface ExamplePanelSpec {
  /** The data query string executed against the configured datasource. */
  query: string;

  /** Optional display unit appended to rendered values (e.g. "ms", "%", "req/s"). */
  unit?: string;
}
