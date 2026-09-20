# Hermes/Maia dev-branch deployment

Concourse pins resource branches at pipeline-definition time. The parallel `dev` lane runs chart/secrets changes in live labs before `master`; production lanes remain out of scope.

| Parameter | Hermes | Maia |
|---|---|---|
| Branch on both repos | `hermes-dev-branch` | `maia-dev-branch` |
| fly target | `ci-monitoring` | `monitoring` |
| Concourse | `https://ci1.eu-de-2.cloud.sap` | `https://ci.eu-de-2.cloud.sap` |
| pipeline directory | `~/gh/secrets/ci/hermes` | `~/gh/secrets/ci/maia` |
| set-pipeline extra | none | `--load-vars-from vars.yaml` |

Both use team `monitoring`, chart `openstack/<stack>`, and labs `qa-de-1`, `qa-de-2`, `qa-de-3`, `eu-de-3`. The branch must exist in both internal `cc/secrets` and public `sapcc/helm-charts`. Dev resources are `secrets-dev.git` and `helm-charts-dev.git`; jobs input-map them over production-named inputs. Jobs are `deploy-all-dev`, `deploy-to-dev-<region>`, and `sync-master-to-dev`.

## Mandatory preflight

```bash
STACK=hermes  # or maia
DEVBRANCH=${STACK}-dev-branch
git -C ~/gh/secrets ls-remote --heads origin "$DEVBRANCH"
git ls-remote --heads https://github.com/sapcc/helm-charts.git "$DEVBRANCH"
grep -n "helm-charts-dev.git\|deploy-all-dev\|${DEVBRANCH}" \
  ~/gh/secrets/ci/${STACK}/pipeline.yaml.erb
```

Stop and name the missing repo if either lookup is empty. Stop if the ERB lacks the dev group. Hermes is known wired; Maia may still depend on unmerged `add-maia-dev-group`, so never assume readiness.

Merge the feature into the shared dev branch with `--no-ff`; never force-push or rewrite it. Validate at least one region and, for release confidence, all dev regions:

```bash
fly -t <target> watch -j ${STACK}/deploy-to-dev-qa-de-1
fly -t <target> trigger-job -j ${STACK}/deploy-all-dev -w
```

Before new work, run `fly -t <target> trigger-job -j ${STACK}/sync-master-to-dev -w`. After validation, merge the original feature to `master` through the normal PR path and confirm `labs` remains healthy.

After `fly -t <target> login`, render `pipeline.yaml.erb`, then set the pipeline:

```bash
fly -t ci-monitoring set-pipeline -p hermes -c pipeline.yaml
fly -t monitoring set-pipeline -p maia -c pipeline.yaml --load-vars-from vars.yaml
```
