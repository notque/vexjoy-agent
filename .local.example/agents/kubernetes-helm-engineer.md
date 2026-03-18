# Kubernetes Helm Engineer (Your Organization's Version)

This is a template for your organization-specific Kubernetes/Helm agent.

## What to Customize

Replace the generic examples below with your actual:
- Internal repository paths
- Helm chart locations
- Service names
- Team conventions

---

## Example Customizations

### Your Helm Charts Location

```bash
# Generic version says: /path/to/helm-charts
# Your version:
cd /home/youruser/projects/infrastructure/helm-charts
```

### Your Internal Services

```yaml
# Generic version uses placeholder service names
# Your version - real services:
services:
  audit: audit-service           # Your audit service
  metrics: prometheus     # Your metrics service
  logging: elasticsearch  # Your logging service
```

### Your Kubernetes Contexts

```bash
# Generic version: kubectl config use-context <context>
# Your version:
kubectl config use-context production-eu-west-1
kubectl config use-context staging-us-east-1
```

### Your Namespace Conventions

```bash
# Generic version: kubectl -n <namespace>
# Your version:
kubectl -n platform-services
kubectl -n monitoring
kubectl -n audit-system
```

---

## Instructions

1. Copy this file to `.local/agents/kubernetes-helm-engineer.md`
2. Replace all placeholders with your real values
3. Add your organization's specific patterns and conventions
4. When you need Kubernetes help, reference this file:
   ```
   "Read .local/agents/kubernetes-helm-engineer.md and help me deploy"
   ```

---

## Template Sections to Fill In

### Your Helm Repository

```bash
helm repo add yourcompany https://charts.yourcompany.com
helm repo update
```

### Your Common Helm Values

```yaml
# values-production.yaml template
global:
  environment: production
  region: # YOUR_REGION

image:
  registry: # YOUR_REGISTRY
  pullPolicy: Always

resources:
  requests:
    memory: "256Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

### Your Deployment Checklist

- [ ] Verify kubectl context is correct
- [ ] Check resource quotas in namespace
- [ ] Review values file for environment
- [ ] Run helm diff before upgrade
- [ ] Verify pods are healthy after deploy
