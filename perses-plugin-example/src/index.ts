import { PanelPlugin } from '@perses-dev/plugin-system';
import { ExamplePanel } from './ExamplePanel';
import { ExamplePanelSpec } from './ExamplePanelTypes';

/**
 * Plugin registration.
 *
 * The `kind` string "ExamplePanel" MUST match:
 *   - The `kind` field in schemas/panels/example-panel/spec.cue
 *   - The `kind` field in any Perses dashboard panel definition referencing this plugin
 */
export const ExamplePanelPlugin: PanelPlugin<ExamplePanelSpec> = {
  PanelComponent: ExamplePanel,
  panelOptionsEditorComponents: [],
  hide: false,
};

export { ExamplePanel } from './ExamplePanel';
export type { ExamplePanelSpec } from './ExamplePanelTypes';
