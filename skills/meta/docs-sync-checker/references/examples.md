# Regression shapes

The checker must distinguish three fixture shapes: a source tool missing from
primary documentation, a documented tool whose source was removed, and malformed
documentation that cannot be parsed. The third is an input failure, not drift.
Use temporary repositories when testing these cases; do not mutate live docs.
