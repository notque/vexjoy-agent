package model

kind: "ExamplePanel"
spec: close({
	// query is the data query string to execute against the datasource.
	// Required — panel cannot render without a target query.
	query: string

	// unit is an optional display unit appended to rendered values (e.g. "ms", "%", "req/s").
	unit?: string
})
