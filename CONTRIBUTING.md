# Contributing

Contributions are welcome when their source and licensing are clear.

## Provenance

- Submit only code and data you have the right to contribute under
  GPL-3.0-or-later.
- Do not copy code from Illumina SpliceAI revisions after v1.3.1 without a
  separate, documented license review.
- Identify any adapted third-party material, its exact source revision, its
  license, and the changes made.
- Do not submit model weights, reference or annotation datasets, raw external
  API responses, patient-derived variants, credentials, or deployment
  containers.

## Developer Certificate of Origin

Every commit must include a `Signed-off-by` line, added with `git commit -s`.
By signing off, the contributor certifies the
[Developer Certificate of Origin 1.1](https://developercertificate.org/).
Contributions are accepted under the repository's GPL-3.0-or-later license.

## Quality checks

Before opening a pull request, run:

```bash
pytest
ruff check .
ruff format --check .
bash -n scripts/slurm/*.sh scripts/validate_outputs.sh
```

Changes that affect scoring, transcript selection, variant generation, or
restart fingerprints should include focused regression tests and appropriate
validation evidence.
