# Validation artifacts

Large VCF outputs are not committed. This directory records immutable input
hashes, comparison summaries, and final validation decisions.

`results/current_mane_v1.5/` contains publication-safe current evidence: the
sanitized run summary, official-comparison JSON, runtime manifest, balanced
64-variant Broad manifest, field-level comparison, and sanitized SNV
production-canary summary. Raw Broad API response caches are intentionally
excluded because their redistribution terms are not expressly stated. The
runtime manifest records `tf32_enabled=false`, runner and source versions, the
determinism environment, and hashes for all five model files.

Older files under `validation/results/` are retained as explicitly historical
engineering evidence.

The source theoretical-variant VCFs and the SpliceAI model files are subject to
their upstream terms and must be obtained separately.
