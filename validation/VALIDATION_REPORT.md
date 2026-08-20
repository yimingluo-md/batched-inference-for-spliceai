# Validation report — 0.1.0rc4

## SNV production canary

- Date: 2026-08-20
- Public source commit: `a145b3c6aeee8fe020033a8a6a0e71816772e73a`
- Platform: Slurm GPU cluster
- GPU: NVIDIA A100-SXM4-80GB
- Parameters: `D=500`, `M=1`, batch 1024, chunk size 16,384
- Annotation: MANE Select v1.5

The current public source passed every SNV production-canary gate:

| Check | Scope | Result |
|---|---:|---:|
| Current generator versus prior generator | 999,999 SNVs | byte-identical |
| Batch-1024 versus deterministic official output | 10,000 SNVs | exact |
| Current scorer versus prior million-record pilot | 999,999 SNVs | byte-identical |
| Input/output record count | 999,999 / 999,999 | passed |
| BGZF and tabix index | one production shard | passed |
| Completion fingerprint and restart | one production shard | verified skip |

The production-sized run completed in 3:18:30, with 11,889.2 application
seconds and 84.11 SNVs/s. The input and output SHA-256 values were:

- input:
  `64c5bc10baf8bf7ddfaf2de9ed383d6ec622ba2200ff229732e41e26ae2ae0db`
- output:
  `7bc6107feee10c85b719cf15a11a1c6c1f16d5bbbc12d7de31bc7b8d3811b338`

The official comparison found zero record-identity, annotation-entry, score,
or position differences and a maximum score difference of 0.00. The public
machine-readable summary is
`validation/results/current_mane_v1.5/snv_production_canary.json`. The indel
production canary remains pending.

## Current release validation

- Date: 2026-07-28
- Platform: Slurm GPU cluster
- GPU: NVIDIA A100-SXM4-80GB
- Parameters: `D=500`, `M=1`, batch 256
- Annotation: MANE Select v1.5
- Official comparator: SpliceAI 1.3.1 with aligned deterministic settings
- TF32: disabled

All current release gates passed.

| Check | Scope | Result |
|---|---:|---:|
| Optimized run | 25,000 SNVs + 25,000 indels | passed |
| Official comparison | 10,000 SNVs + 10,000 indels | exact |
| Repeat determinism | 25,000 SNVs + 25,000 indels | byte-identical |
| Broad Lookup API | 64 balanced variants | 64/64 exact |
| Restart smoke test | completed 64-record shard | verified skip |
| Runtime manifest | TF32, determinism, five model hashes | complete |

The official comparison found zero record-identity differences, zero missing
or differing annotation entries, zero score-field differences, and zero
position-field differences. Maximum score difference was 0.00.

Broad validation used 32 SNVs and 32 indels, 32 plus-strand and 32 minus-strand
variants, 64 distinct genes, and all 24 primary chromosomes. All 64 requested
rows were numerically compared; all score and position fields matched exactly.
TLS certificate verification remained enabled.

The optimized outputs repeated byte-for-byte:

- SNV:
  `042bd9a286445eecda74488328ddafbb39b2b4d6f9cdb827347b6ed011d41339`
- indel:
  `f93aced1dd78249e91d147882fbe5a506436e10a2b7f4ac8d0499e082e60c787`

The 50,000-record optimized and repeat runs used commit `6c279a5`; the matched
20,000-record optimized comparison and runtime manifest used `b106890`. The
intervening commits changed the official-comparison wrapper and Slurm
submission path, not optimized scoring. The official wrapper used `2b6b4ce`;
the subsequent `b106890` change was limited to submission orchestration.
Machine-readable, publication-safe evidence is under
`validation/results/current_mane_v1.5/`.
See `validation/SOURCE_PROVENANCE.md` for the clean-history transition and
source-equivalence record.

## Historical report

The material below records the earlier 2026-07-25 validation. It predates the
current rerun and is retained as engineering history.

Date: 2026-07-25
Platform: Slurm GPU cluster
GPU: NVIDIA A100 80 GB
Parameters: `D=500`, `M=1`, batch 256
Official comparator: SpliceAI 1.3.1 CLI with deterministic seeds
Optimized runner: historical release candidate

## MANE v1.5 and Broad API addendum

The production annotation was updated from historical MANE Select v1.0 to the
current MANE Select v1.5 release. The primary-assembly conversion contains
19,299 transcripts/genes, 202,335 exons, and 24 contigs. It deliberately
excludes 64 MANE Select transcripts represented only on GRCh38 patch or
alternate contigs. Source and converted SHA-256 hashes are recorded in
`validation/mane_v1.5_manifest.json`.

GPU validation run 25999220 scored all 64 strand/type-balanced candidates with
`D=500`, `M=1` in 39.40 seconds of application wall time. An eight-variant
nonzero-score subset was compared with Broad's GRCh38 SpliceAI Lookup API:

| Check | Result |
|---|---:|
| Matching MANE Select response | 8/8 |
| Delta-score fields compared | 32 |
| Differing delta-score fields | 0 |
| Maximum score difference | 0.00 |
| Delta-position fields compared | 32 |
| Differing delta-position fields | 0 |

The subset contained two variants in each plus/minus-strand and SNV/indel
category. The machine-readable comparison is retained under
`validation/results/broad_mane_v1.5/`; raw API response caches are excluded
from publication.

## Scope

- 100,000 optimized records:
  - 25,000 SNVs and 25,000 indels with GENCODE v24
  - 25,000 SNVs and 25,000 indels with MANE Select v1.0
- 20,000 matched official-versus-optimized records:
  - 5,000 SNVs and 5,000 indels per annotation
- 50,000 corrected repeat records for deterministic verification
- Chromosomes 1–22, X, and Y
- Both transcript strands
- Transcript and internal exon boundaries
- Multi-annotation records
- SNVs, one-base insertions, and one- through four-base deletions

## Official comparison

| Annotation | Type | Records | Exactly identical records | Differing records | Missing entries | Differing score fields | Maximum score difference | Differing position fields | Nontrivial position differences |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| GENCODE v24 | SNV | 5,000 | 4,998 | 2 | 0 | 0 | 0.00 | 2 | 0 |
| GENCODE v24 | indel | 5,000 | 4,964 | 36 | 0 | 1 | 0.01 | 38 | 0 |
| MANE v1.0 | SNV | 5,000 | 4,989 | 11 | 0 | 0 | 0.00 | 11 | 0 |
| MANE v1.0 | indel | 5,000 | 4,975 | 25 | 0 | 5 | 0.01 | 22 | 0 |
| **Total** |  | **20,000** | **19,926** | **74** | **0** | **6** | **0.01** | **73** | **0** |

Pass criteria:

- Record identities: passed
- Annotation entry sets: passed
- Maximum formatted delta-score difference ≤0.01: passed
- Position differences restricted to associated scores ≤0.01: passed

The 74 differing records represent 0.37% of the comparison set. Differences
are consistent with floating-point batching effects and argmax choices among
effectively tied, negligible scores.

## Determinism

Corrected 25,000-record GENCODE jobs were repeated:

- SNV outputs were byte-identical:
  `c640742990098916361f43c783ede2860b7c9353af701e0dba890cbd26f0da56`
- Indel outputs were byte-identical:
  `847e2646517755b2933aaedd9fc485e670a183091bfb2aef3a561dbaf86d097a`

## Restartable shard smoke test

The release `run_shard.sh` completed job 25978187 successfully on 2,000
records. It produced a BGZF VCF, tabix index, metadata, timing log, SHA-256
checksum, matching input/output record counts, and an atomic completion marker.
Output SHA-256:
`08b93465ab72684901ab541d858127e1de29b67d68ed476309f08f6e840f5821`.

## Performance on matched 5,000-record samples

| Annotation | Type | Official wall time | Optimized wall time | Wall-time speedup |
|---|---|---:|---:|---:|
| GENCODE v24 | SNV | 32:53 | 1:13 | 27.1× |
| GENCODE v24 | indel | 34:07 | 1:33 | 22.0× |
| MANE v1.0 | SNV | 20:30 | 1:00 | 20.7× |
| MANE v1.0 | indel | 20:10 | 1:02 | 19.6× |

## Defect discovered before release

The initial prototype did not reverse minus-strand prediction positions back
into forward genomic coordinate order after model inference. The stratified
audit exposed this defect: 12,262/25,000 SNVs and 12,234/25,000 indels changed
after correction. Pre-fix outputs are explicitly invalid. All results reported
above were generated after the correction.

## Historical decision

The implementation tested in this report passed the defined numerical, structural,
determinism, diversity, and performance gates for an experimental research
release. The later upstream-compatibility corrections have now been covered by
the current validation reported above. GPL-era SpliceAI 1.3.1 provenance is
documented in `docs/LICENSE_REVIEW.md`.
