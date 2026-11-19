# Perses Reference

> **Scope**: The Perses observability platform itself: dashboards, plugins, operator, and core development.
> **Not here**: Grafana or Prometheus dashboards, alerting, and PromQL (`prometheus-grafana.md`); Kubernetes manifests and Helm charts unrelated to Perses (`kubernetes-helm.md`); TypeScript frontend work outside the Perses codebase (`frontend` skill). For Go backend or TypeScript code inside Perses, also load the `programming` or `frontend` skill.

## Areas

- **Core**: Go backend (API handlers, storage, auth), React/TypeScript frontend (dashboard editor, panel rendering), CUE schemas, build system, contribution workflow.
- **Dashboards**: dashboard lifecycle, Dashboard-as-Code (CUE/Go SDK), PromQL/LogQL/TraceQL queries, `percli`, MCP integration, 27 official plugins, CI/CD pipelines.
- **Operator**: Perses Operator CRDs (v1alpha2), Deployment vs StatefulSet, Helm charts, cert-manager, RBAC, monitoring, multi-instance management.
- **Plugins**: plugin architecture (Module Federation, CUE schemas, archive distribution), plugin types (Panel, Datasource, Query, Variable, Explore), `percli plugin` commands, Grafana migration schemas.

## Verification stops

- After designing or changing a dashboard: have I checked it against the existing datasources and available metrics? A dashboard that references a missing datasource or metric fails silently.
- After changing CRDs, Helm values, or operator config: have I checked for breaking changes in dependent dashboards and datasource configs?

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| dashboard, DaC, Dashboard-as-Code, percli, variable, query, datasource, PromQL, panel, timeseries, migrate Grafana | [perses/dashboard.md](perses/dashboard.md) | Dashboard creation and DaC SDK patterns |
| Kubernetes, CRD, operator, Helm, k8s, PersesDashboard, PersesProject, RBAC, cert-manager, manifest | [perses/operator.md](perses/operator.md) | Kubernetes operator CRDs and deployment |
| plugin, Module Federation, CUE schema, scaffold, panel plugin, datasource plugin, percli plugin, webpack | [perses/plugin.md](perses/plugin.md) | Plugin development, CUE schemas, React components |
