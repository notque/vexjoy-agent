# Change-surface verification

Load only the sections touched by the diff. Repository commands and CI policy
override examples.

## Schema or migration

- Capture schema/migration state before and after; diff the structures, not only
  migration exit codes.
- Search models, raw SQL, serializers, fixtures, and consumers for renamed or
  removed fields.
- Exercise forward migration on representative data and rollback when rollback
  is promised. Verify preservation, defaults, constraints, indexes, and duplicate
  or near-equivalent existing fields.

## Public API or serialized format

- Compare generated schema/contracts and representative old/new payloads.
- Test missing, extra, null, boundary, and invalid fields plus status/error shape.
- Check known consumers and compatibility policy; a compiling producer does not
  establish consumer compatibility.

## Configuration or infrastructure

- Render/parse the effective configuration for the target environment.
- Verify secret references without printing values.
- Exercise startup, health/readiness, shutdown, and rollback path where changed.
- Confirm generated manifests/images contain the intended artifact and version.

## Cross-component integration

Trace one representative value through producer, transport/storage, reader, and
observable action. Establish exists → substantive → wired → data flows. Mocks
can prove caller behavior but not deployed wiring.

## Documentation or examples

Run executable snippets when practical; validate local links and referenced
paths. Confirm flags, output shapes, and defaults against the live command.

Report each applicable gate as pass, fail, or unrun with command/observation,
scope, exit status, and retained diagnostic location.
