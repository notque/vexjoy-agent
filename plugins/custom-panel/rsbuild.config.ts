import { defineConfig } from "@rsbuild/core";
import { pluginReact } from "@rsbuild/plugin-react";

export default defineConfig({
  plugins: [pluginReact()],
  tools: {
    rspack: {
      output: {
        uniqueName: "custom-panel-plugin",
      },
    },
  },
  moduleFederation: {
    options: {
      name: "CustomPanelPlugin",
      filename: "remoteEntry.js",
      exposes: {
        ".": "./src/index.ts",
      },
      shared: {
        react: { singleton: true, requiredVersion: "^18.2.0" },
        "react-dom": { singleton: true, requiredVersion: "^18.2.0" },
        "@perses-dev/core": { singleton: true },
        "@perses-dev/plugin-system": { singleton: true },
      },
    },
  },
});
