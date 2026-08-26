# Changelog

## Unreleased

- Made nested Slurm submissions fail before GPU allocation when the shard
  runner resolves to a transient or otherwise non-executable path.
- Completed the current-public-source SNV production canary: a 999,999-record
  batch-1024 run was byte-identical to the prior million-record pilot, matched
  the deterministic official comparator exactly on 10,000 stratified SNVs,
  and passed BGZF, tabix, record-count, checksum, and restart-skip gates.
- Renamed the project to "Batched inference for SpliceAI" while preserving the
  `spliceai-batched` Python distribution and command names for compatibility.
- Expanded the licensing audit to cover source ancestry, later Illumina
  relicensing, examined forks, model/output boundaries, direct dependencies,
  external validation evidence, naming, and clinical-use limitations.
- Added contributor provenance rules and Developer Certificate of Origin
  sign-off requirements.
- Removed raw Broad Lookup API response caches because their output-data
  redistribution terms are not explicit; retained the reproducible query
  manifest and aggregate/field-level comparison evidence.
- Re-rooted the public history under GPL-3.0-or-later and removed obsolete
  private release-candidate tags and branches that carried temporary licensing
  language or unrelated institutional metadata.
- Bumped the source version to 0.1.0rc4.
- Added a deterministic, reference-derived MANE variant-universe planner and
  generator for clean SNV and bounded 1–4 bp indel VCF shards.
- Added restartable Slurm CPU-array scripts and scoring-manifest finalization
  for the generated universe.
- Added explicit array start/end ranges for staged preprocessing and scoring
  submissions.
- Added explicit container bind paths and package `PYTHONPATH`, and fingerprinted
  the complete imported runner package rather than only the CLI file.
- Resolved container-facing runner, annotation, reference, and image paths
  through filesystem symlinks before hashing, binding, and execution.
- Added recorded, site-configurable extra container binds for externally
  mounted GPU runtime libraries.
- Preserved annotation contig names in generated VCFs while resolving separate
  FASTA contig names for reference-sequence access.
- Distinguished the legacy precomputed-resource compute projection from the
  authoritative production plan.
- Completed current-code validation: 50,000 optimized records, exact
  20,000-record official comparison, byte-identical SNV and indel repeats,
  restart smoke test, and 64/64 exact Broad Lookup API comparisons.
- Added a publication-safe current validation bundle with the runtime manifest,
  query manifest, and field-level summaries; raw Broad response caches remain
  local and are excluded from distributions.
- Added a public disclosure of AI-assisted development.
- Made the Broad validation gate fail closed when a requested row is unscored
  or otherwise not numerically compared.
- Applied the same TensorFlow/cuDNN determinism environment before TensorFlow
  import in both optimized and official-comparison entry points.
- Added prediction cardinality and ensemble-shape checks to prevent silent
  annotation loss from unexpected model output.
- Added runner version, git commit, annotation provenance, and labeled
  GPU/driver fields to production metadata.
- Replaced the removed `pkg_resources` runtime dependency with
  `importlib.metadata` and `importlib.resources`, retaining a Python 3.7
  fallback.
- Disabled TF32 before model loading in both the optimized runner and a new
  official-SpliceAI comparison wrapper, and recorded its effective state.
- Moved shared-asset hashing to array submission, added optional per-input
  manifest hashes, and included the container SHA-256 in restart fingerprints.
- Made unscored MNV Broad comparisons, one-record sampling, and malformed VCF
  rows produce explicit, controlled outcomes.
- Marked the MANE v1.5 Broad result as historical pending current-code reruns.
- Fixed Slurm array manifest parsing under `/bin/sh` and added missing-task
  validation.
- Added verified completion-marker restart skips.
- Restored SpliceAI 1.3.1 deletion precision and positive-zero formatting.
- Preserved existing SpliceAI annotations when a record receives no new score.
- Compacted one-hot inputs to `uint8` before retaining and batching them.
- Made deterministic TensorFlow settings apply to direct CLI invocation.
- Restored Setuptools 68 build compatibility while retaining license files.
- Completed the GPLv3 license text and ignored uncompressed VCF outputs.
- Marked recorded GPU validation as historical pending corrected-code reruns.
- Removed personal and platform-specific attribution language.
- Replaced cluster-specific orchestration with configurable Slurm helpers.
- Removed the reproducibility-contract section from the README.
- Sanitized validation filenames and environment-specific paths.

## 0.1.0rc3 — 2026-07-28

- Recorded exact SpliceAI 1.3.1 GPL-era source provenance.
- Replaced the temporary no-redistribution notice with GPL-3.0-or-later.
- Added Illumina attribution and prominent modified-work notices.
- Removed obsolete review and permission-request release blockers.
- Completed the public-release license audit.

## 0.1.0rc2 — 2026-07-25

- Updated the production annotation to MANE Select v1.5.
- Made primary-assembly filtering explicit for MANE patch/alternate records.
- Added a restartable, rate-limited Broad SpliceAI Lookup API validator.
- Verified eight balanced MANE v1.5 SNV/indel and plus/minus-strand variants
  with exact delta-score and delta-position agreement.

## 0.1.0rc1 — 2026-07-24

- Added batched five-model inference.
- Added reference-prediction reuse across alternate alleles.
- Added length-grouped indel inference.
- Added deterministic execution settings and restartable Slurm shards.
- Added stratified sampling and VCF comparison utilities.
- Added test, benchmark, validation, and licensing documentation.
- Corrected post-prediction coordinate orientation for minus-strand
  transcripts before any public release.
