// Copyright 2024 The Perses Authors
// Licensed under the Apache License, Version 2.0
//
// migrate.cue maps a Grafana "stat" panel definition to a Perses CustomPanel spec.
// Supported Grafana panel types: stat, singlestat
//
// Unsupported Grafana fields (no direct equivalent in CustomPanel):
//   - options.graphMode
//   - options.colorMode
//   - options.justifyMode
//   - fieldConfig.defaults.mappings

package migrate

import (
	"github.com/perses/perses/cue/schemas/panels/migrate"
)

migrate.#Panel & {
	// target is the resulting Perses panel spec after migration.
	target: {
		kind: "CustomPanel"
		spec: {
			// Map the Grafana panel title to the Perses title field.
			title: grafana.title

			// Map the Grafana unit override if present.
			if grafana.fieldConfig.defaults.unit != _|_ {
				unit: grafana.fieldConfig.defaults.unit
			}

			// Map Grafana threshold steps to Perses threshold steps.
			if grafana.fieldConfig.defaults.thresholds.steps != _|_ {
				thresholds: [
					for step in grafana.fieldConfig.defaults.thresholds.steps
					if step.value != _|_ {
						value: step.value
						color: step.color
					},
				]
			}
		}
	}
}
