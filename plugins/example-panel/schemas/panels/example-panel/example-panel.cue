// Copyright 2024 The Perses Authors
// Licensed under the Apache License, Version 2.0

package model

kind: "ExamplePanel"
spec: close({
	// text is the message displayed in the center of the panel.
	// Defaults to "Hello from ExamplePanel" when omitted.
	text: string | *"Hello from ExamplePanel"

	// color is a CSS-compatible color string applied to the text.
	// Accepts any valid CSS color: hex (#333333), named (red), rgb(...).
	color: string | *"#333333"

	// fontSize controls text size in pixels. Clamped to the range 10–72.
	fontSize: int & >=10 & <=72 | *16

	// align controls horizontal text alignment within the panel.
	align: "left" | "center" | "right" | *"center"
})
