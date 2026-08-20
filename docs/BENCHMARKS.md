# Benchmarks

Date: 2026-07-24
Platform: Slurm GPU cluster
GPU: NVIDIA A100 80 GB
SpliceAI: 1.3.1, five official models
Reference: UCSC hg38
Annotation: bundled GENCODE v24 canonical GRCh38
Parameters: `D=500`, `M=1`

## Stock CLI

The measurements include container/model startup.

| Variant type | Records | Wall time | Throughput |
|---|---:|---:|---:|
| SNV | 200 | 100.21 s | 2.00 variants/s |
| Indel | 200 | 107.76 s | 1.86 variants/s |

## Batched runner

The model-phase rate includes VCF preparation, reference-sequence extraction,
five-model prediction, and score formatting after the models are loaded.

| Variant type | Batch | Records | Model-phase rate | Total wall |
|---|---:|---:|---:|---:|
| SNV | 128 | 2,000 | 67.81/s | 45.03 s |
| SNV | **256** | 2,000 | **72.96/s** | **40.60 s** |
| SNV | 512 | 2,000 | 70.01/s | 41.69 s |
| Indel | 128 | 2,000 | 59.63/s | 50.24 s |
| Indel | **256** | 2,000 | **61.53/s** | **46.05 s** |
| Indel | 512 | 2,000 | 61.43/s | 45.78 s |

Batch 256 is the current production default. Batch 128 and batch 256 produced
exactly identical annotations across the 4,000 benchmark records.

On the corrected, matched 5,000-record stratified samples, end-to-end wall-time
speedups versus the deterministic official CLI were 27.1× for GENCODE SNVs,
22.0× for GENCODE indels, 20.7× for MANE SNVs, and 19.6× for MANE indels.

Current MANE Select v1.5 validation on matched 10,000-record samples measured
26.2× end-to-end wall-time speedup for SNVs (101.03 versus 2,643.36 seconds)
and 25.6× for indels (102.01 versus 2,606.60 seconds). Both optimized outputs
were exactly identical to the deterministic official SpliceAI 1.3.1 outputs.

## SNV production canary

The 2026-08-20 current-public-source canary used MANE Select v1.5, `D=500`,
`M=1`, batch 1024, chunk size 16,384, and an A100 80 GB GPU. It processed
999,999 reference-derived SNVs in 11,889.2 application seconds (84.11/s) and
completed the full indexed, checksummed shard in 3:18:30. The 10,000-record
stratified batch-1024 output was exactly identical to the deterministic
official SpliceAI 1.3.1 output: zero record, annotation, score, or position
differences.

The canary input and output were byte-identical to the earlier million-record
pilot:

- input SHA-256:
  `64c5bc10baf8bf7ddfaf2de9ed383d6ec622ba2200ff229732e41e26ae2ae0db`
- output SHA-256:
  `7bc6107feee10c85b719cf15a11a1c6c1f16d5bbbc12d7de31bc7b8d3811b338`

The immutable SNV plan contains 3,419 shards and 3,409,598,145 records.
At the measured canary rate, the idealized total is approximately 11,261
A100-hours (1.29 A100 GPU-years):

| Concurrent A100 GPUs | Idealized SNV compute time |
|---:|---:|
| 16 | 29.3 days |
| 32 | 14.7 days |
| 64 | 7.3 days |
| 96 | 4.9 days |

Measured compression extrapolates to approximately 8.2 GB of generated SNV
inputs and 35.7 GB of scored outputs, excluding indexes, metadata, logs,
temporary copies, retries, and safety margin. Queueing, fair-share, and
shared-filesystem contention are also excluded from the compute projection.

## Legacy-resource projection

The following counts came from the 2019 precomputed input resources:

- SNVs: 3,433,384,833
- Indels: 9,155,870,805
- Total: 12,589,255,638

At the batch-256 model-phase rates:

- SNVs: 1.49 A100 GPU-years
- Indels: 4.72 A100 GPU-years
- Total: 6.21 A100 GPU-years

| Concurrent A100 GPUs | Idealized compute time |
|---:|---:|
| 16 | 142 days |
| 32 | 71 days |
| 64 | 35 days |
| 128 | 18 days |

These projections exclude queueing, fair-share, shared-filesystem contention,
retries, validation, and final merging.

The production run now uses a clean, reference-derived MANE Select v1.5
variant universe. Its immutable generation plan supplies the authoritative
record counts. The authoritative SNV projection is reported above. Recalculate
the indel projection from its plan and production-sized pilot before the indel
array is submitted; do not treat the legacy-resource counts as final.

## Interpretation

Do not compare the small stock wall-time rate directly with a production shard
without accounting for startup amortization. Production shards should contain
approximately 1–5 million records. Start production in bounded waves so
concurrency and shared-filesystem behavior are measured before the full array
is released.
