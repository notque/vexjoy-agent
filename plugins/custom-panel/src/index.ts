import { PanelPlugin } from "@perses-dev/plugin-system";
import { CustomPanelComponent } from "./PanelComponent";
import { CustomPanelSpec } from "./types";

/**
 * Plugin registration.
 *
 * The `kind` string "CustomPanel" MUST match:
 *   - The `kind` field in schemas/panels/custom-panel/custom-panel.cue
 *   - The `kind` field in any Perses dashboard panel definition referencing this plugin
 */
export const CustomPanelPlugin: PanelPlugin<CustomPanelSpec> = {
  PanelComponent: CustomPanelComponent,
  panelOptionsEditorComponents: [],
  hide: false,
};

export { CustomPanelComponent } from "./PanelComponent";
export type { CustomPanelSpec, ThresholdStep } from "./types";
