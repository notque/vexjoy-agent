# Vault Examples (Your Organization's Version)

This is a template for your organization-specific Vault examples.

## What to Customize

Replace the generic examples below with your actual:
- Vault server URLs
- Authentication methods
- Secret paths
- Policy examples

---

## Your Vault Configuration

### Server URL

```bash
# Generic: https://vault.example.com
export VAULT_ADDR="https://vault.yourcompany.com"
```

### Authentication

```bash
# Generic: vault login
# Your method (e.g., OIDC, LDAP, AppRole):
vault login -method=oidc role=developer
```

### Your Secret Paths

```bash
# Generic: secret/data/myapp
# Your actual paths:
vault kv get secret/platform/database/production
vault kv get secret/services/api-keys/stripe
vault kv get secret/infrastructure/certificates/wildcard
```

---

## Your Common Operations

### Read a Secret

```bash
# Your team's common secrets:
vault kv get -format=json secret/your-team/app-config | jq -r '.data.data'
```

### Write a Secret

```bash
vault kv put secret/your-team/new-secret \
  api_key="your-api-key" \
  api_secret="your-api-secret"
```

### List Secrets

```bash
vault kv list secret/your-team/
```

---

## Your Policies

### Developer Policy Template

```hcl
# developer-policy.hcl
path "secret/data/your-team/*" {
  capabilities = ["read", "list"]
}

path "secret/data/shared/*" {
  capabilities = ["read"]
}
```

### Service Account Policy Template

```hcl
# service-policy.hcl
path "secret/data/services/{{identity.entity.name}}/*" {
  capabilities = ["read"]
}
```

---

## Instructions

1. Copy this file to `.local/skills/vault-helper/references/examples.md`
2. Replace all placeholders with your real Vault configuration
3. Add your organization's specific patterns
4. When you need Vault help, the skill will use your examples
