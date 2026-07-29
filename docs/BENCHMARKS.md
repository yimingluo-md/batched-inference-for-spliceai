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
record counts. Recalculate the GPU-year and storage projections from that plan
and from one production-sized SNV and indel pilot before global submission;
do not treat the legacy-resource counts above as the final production totals.

## Interpretation

Do not compare the small stock wall-time rate directly with a production shard
without accounting for startup amortization. Production shards should contain
approximately 1–5 million records and should be benchmarked under the intended
concurrency before global submission.
