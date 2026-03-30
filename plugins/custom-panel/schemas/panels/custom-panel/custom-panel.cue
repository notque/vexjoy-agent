// Copyright 2024 The Perses Authors
// Licensed under the Apache License, Version 2.0

package model

kind: "CustomPanel"
spec: close({
	// title is the display label rendered at the top of the panel.
	title: string

	// unit controls how numeric values are formatted (e.g. "bytes", "percent", "short").
	unit?: string

	// thresholds defines a list of color-coded threshold steps.
	// Each step specifies a numeric value and a display color.
	thresholds?: [...#ThresholdStep]
})

// ThresholdStep pairs a numeric boundary with a display color.
#ThresholdStep: {
	// value is the lower boundary of this threshold band.
	value: number
	// color is a CSS-compatible color string (e.g. "#e02f44", "green").
	color: string
}
