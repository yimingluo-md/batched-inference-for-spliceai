# Reproducibility

For each production release, retain a machine-readable run manifest containing:

```text
runner_version
git_commit
spliceai_version
model_sha256_1 ... model_sha256_5
container_digest
reference_path
reference_sha256
annotation_path
annotation_release
annotation_source_url
annotation_source_sha256
annotation_sha256
distance
mask
batch_size
chunk_records
gpu_model
driver_version
tf32_enabled
input_sha256
input_records
output_sha256
output_records
started_at
finished_at
```

Shard manifests are immutable inputs. A shard is complete only when its output
VCF, tabix index, record-count check, SHA-256 checksum, and completion marker
all exist. On resubmission, `run_shard.sh` skips a completed shard only after
verifying the marker identity, output and index presence, output checksum, and
indexed record count. The marker also includes a fingerprint of the input,
reference, annotation, runner, container SHA-256, runtime, and
scoring/batching parameters, so outputs made by an older runner, replaced
container, or changed configuration are rerun. An incomplete or inconsistent
completion state is rerun.

The array submitter hashes shared reference, annotation, the complete Python
runner package, and the container once and passes those digests to every task.
A third, optional
`input_sha256` column in the shard manifest avoids rehashing each input during
resubmission. Two-column manifests remain supported and cause each task to hash
its own input.

`spliceai-batched-runtime` records the effective TF32 state and the SHA-256 and
size of all five installed model files, the installed runner version, the git
commit supplied through `SPLICEAI_BATCHED_GIT_COMMIT`, and the effective
TensorFlow determinism environment. The optimized runner and
`spliceai-batched-official` apply the same determinism environment and disable
TF32 before loading TensorFlow or SpliceAI.

`submit_array.sh` derives `runner_version` and `git_commit` from the checked-out
runner when possible and passes them to every shard. Set `RUNNER_VERSION` and
`GIT_COMMIT` explicitly when submitting a copied runner outside its repository.
The package-tree SHA-256 is part of the restart fingerprint, so modifying an
imported runner module invalidates an older completion marker. The runner also
binds its package, reference, annotation, and node-local working directory into
the container explicitly using physical paths (resolving filesystem symlinks)
and supplies the package root through `PYTHONPATH`.
Sites whose GPU libraries are mounted outside the container can set
`CONTAINER_EXTRA_BIND_PATHS` to a colon-separated directory list; the exact value is
recorded in every shard's metadata.
For a production annotation, also set `ANNOTATION_RELEASE`,
`ANNOTATION_SOURCE_URL`, and `ANNOTATION_SOURCE_SHA256`. The shard metadata uses
the exact field names above, including labeled `gpu_model` and
`driver_version` values.
