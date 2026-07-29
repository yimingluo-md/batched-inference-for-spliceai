# Validation protocol

> **Current status (2026-07-28):** Current-code validation passed. The optimized
> runner and official comparator used the same deterministic TensorFlow/cuDNN
> policy with TF32 disabled. The evidence covers 50,000 optimized records,
> 20,000 exact official comparisons, byte-identical repeats, a restart smoke
> test, and 64 exact Broad Lookup API comparisons.

## Release gates

1. Compare at least 10,000 stratified records against the official SpliceAI
   1.3.1 CLI.
2. Run the optimized implementation on at least 50,000 stratified records.
3. Include all primary chromosomes, both transcript strands, transcript
   boundaries, internal exon boundaries, SNVs, insertions, and deletions.
4. Require identical VCF record identities and identical annotation-entry sets.
5. Require maximum formatted delta-score difference no greater than 0.01.
6. Review every differing delta position and confirm it arises from an
   effectively tied prediction.
7. Repeat one optimized configuration and require byte-identical output.
8. Validate compressed output, tabix indexing, input/output record counts, and
   shard completion markers.
9. Compare at least 64 chromosome/strand/type-balanced variants with Broad's
   rate-limited SpliceAI Lookup API using the production MANE release.
10. Record `tf32_enabled=false`, the five model hashes, and the container
    SHA-256 in the current runtime/run manifests.
11. Require `comparisons_performed == queries` for the Broad subset; an
    unscored or otherwise non-comparable local row fails the gate.

## Sampling

The deterministic sampler divides annotations by primary chromosome and strand,
selects transcript quantiles across each stratum, and samples around transcript
starts, transcript ends, and internal exon boundaries. Records are finally
downsampled evenly so later chromosomes are not truncated.

Current samples:

| Type | Records | Chromosomes | Use |
|---|---:|---:|---|
| SNV | 25,000 | 24 | optimized validation |
| Indel | 25,000 | 24 | optimized validation |
| SNV | 10,000 | 24 | official comparison |
| Indel | 10,000 | 24 | official comparison |

No patient or controlled data are included.

The 25,000-indel sample contains 13,147 one-base insertions and 11,853
deletions spanning lengths one through four. Each 25,000-record sample is
nearly uniform across chromosomes 1–22, X, and Y (1,041–1,042 records per
chromosome).

GENCODE overlap characterization confirms 12,262 minus-strand SNVs and 12,234
minus-strand indels, in addition to the corresponding plus-strand records.
The corrected output also includes 95 multi-annotation SNV records and 87
multi-annotation indel records. MANE outputs include 43 multi-annotation
records of each type.

## Current MANE Select v1.5 results

All current release gates passed:

- 25,000 SNVs and 25,000 indels completed with matching input/output counts.
- Repeated SNV and indel outputs were byte-identical.
- 10,000 SNVs and 10,000 indels were exactly identical to the deterministic
  official SpliceAI 1.3.1 wrapper: zero record, annotation, score, or position
  differences and maximum score difference 0.00.
- A completed 64-record shard was verified and skipped on resubmission.
- The runtime manifest reports `tf32_enabled=false`, the aligned determinism
  environment, and SHA-256 hashes for all five model files.

The 25,000-record optimized wall times were 226.76 seconds for SNVs and 203.66
seconds for indels. On the matched 10,000-record comparison samples, optimized
versus official wall times were 101.03 versus 2,643.36 seconds for SNVs and
102.01 versus 2,606.60 seconds for indels.

The 25,000-record optimized and deterministic-repeat outputs had these SHA-256
values:

- SNV: `042bd9a286445eecda74488328ddafbb39b2b4d6f9cdb827347b6ed011d41339`
- indel: `f93aced1dd78249e91d147882fbe5a506436e10a2b7f4ac8d0499e082e60c787`

Machine-readable summaries, the runtime manifest, the 64-variant query
manifest, and field-level comparison evidence are in
`validation/results/current_mane_v1.5/`. Raw API response caches are excluded
because the service's output-redistribution terms are not explicit.

## Historical results

Earlier validation:

- Same batch size repeated: byte-identical output.
- Batch 128 versus batch 256: 0 differences in 2,000 SNVs.
- Batch 128 versus batch 256: 0 differences in 2,000 indels.
- Optimized versus stock on 200 SNVs: four records differed, with maximum
  formatted delta-score difference 0.01 and one tied-position difference.
- Repeated stock/GPU runs showed the same scale of numerical variation.

During the stratified source audit, the release candidate was found to be
missing the official post-prediction coordinate reversal for minus-strand
transcripts. This was not exercised by the original chromosome-1/OR4F5
benchmark. The defect was corrected before release; all optimized stratified
jobs must be rerun with the corrected commit. Pre-fix optimized outputs are
invalid and must not be used scientifically.

Corrected optimized validation completed:

- GENCODE v24: 25,000 SNVs and 25,000 indels, all 24 primary chromosomes.
- MANE v1.0: 25,000 SNVs and 25,000 indels, all 24 primary chromosomes.
- Input/output record counts matched for all four runs.
- Corrected GENCODE runs repeated byte-for-byte identically:
  - SNV SHA-256:
    `c640742990098916361f43c783ede2860b7c9353af701e0dba890cbd26f0da56`
  - indel SHA-256:
    `847e2646517755b2933aaedd9fc485e670a183091bfb2aef3a561dbaf86d097a`

Official-reference comparison passed across 20,000 matched records. Record
identities and annotation-entry sets were identical. Of 20,000 records, 74
differed: six formatted score fields differed by at most 0.01, and 73 position
fields differed only where the associated score was at most 0.01. See
`validation/VALIDATION_REPORT.md` and the machine-readable JSON/detail files in
`validation/results/`.

## Current production annotation: MANE Select v1.5

Performance benchmarks use the built-in GENCODE v24 annotation to isolate
implementation behavior. The scientific production run should use a
checksum-pinned SpliceAI-compatible MANE Select v1.5 annotation.

The MANE conversion must be independently verified for:

- 0-based transcript and exon starts;
- end-coordinate convention;
- chromosome naming;
- strand;
- gene-symbol output;
- exon ordering;
- exactly one intended MANE Select transcript per gene;
- expected row and transcript counts.

Pinned source:

- MANE release: 1.5
- NCBI RefSeq annotation release: `GCF_000001405.40-RS_2025_08`
- Ensembl release: 116
- source file: `MANE.GRCh38.v1.5.ensembl_genomic.gtf.gz`
- source URL:
  `https://ftp.ncbi.nlm.nih.gov/refseq/MANE/MANE_human/release_1.5/MANE.GRCh38.v1.5.ensembl_genomic.gtf.gz`
- source SHA-256:
  `71d4b3c89c9d948683bf0db5d81b00d9ae9f3b943177b74cbd87e68f08e34d66`
- converted annotation SHA-256:
  `e323dddd489bcde6b5016776ccb1dd6955bb62c5af576c120f7b9815be2bdd53`
- UCSC hg38 FASTA SHA-256:
  `d2b7be348fb20af46461855faec64dfbd21532620bd125783df050180446055e`
- FASTA index SHA-256:
  `eb7e1fea3ac1c264d6f21a1358727ef533ad560634b0ef360818d970c5f09687`
- primary-assembly MANE Select transcripts: 19,299
- gene symbols: 19,299
- primary contigs: 24
- exons: 202,335
- MANE Select transcripts excluded because they are patch/alternate-only: 64

The current external validation used 64 distinct genes in a balanced design:
32 SNVs and 32 indels, 32 plus-strand and 32 minus-strand records, spanning all
24 primary chromosomes. Against Broad's GRCh38 SpliceAI Lookup API:

- all 64/64 requested genes had exactly one matching MANE Select response;
- all 64/64 requested rows were numerically compared;
- all 256 delta-score fields were identical;
- all 256 delta-position fields were identical;
- maximum score difference was 0.00;
- reported `distance=500` and `mask=1` parameters matched for all responses;
- normal TLS certificate verification remained enabled.

The public endpoint was queried sequentially with a rate-limiting delay and
response caching. The validator passed only after confirming
`comparisons_performed == queries`.

Reproduce the API comparison with:

```bash
spliceai-batched-broad \
  --vcf mane.v1.5.output.vcf \
  --manifest queried_variants.tsv \
  --output-dir broad-validation \
  --distance 500 \
  --mask 1 \
  --delay-seconds 20
```

Use `--insecure` only when a trusted TLS interception proxy makes normal
certificate validation impossible. Current machine-readable summaries and the
64-variant query manifest are in
`validation/results/current_mane_v1.5/broad/`; raw response caches are not
distributed.

Run the official comparison through `spliceai-batched-official`, not the
upstream `spliceai` console script directly, so both sides use the same
TensorFlow/cuDNN determinism environment and have TF32 disabled.

## Historical MANE Select v1.0 validation

The earlier 100,000-record/official-CLI release validation used MANE v1.0 and
remains valid implementation evidence, but v1.0 is no longer the production
annotation. Its source SHA-256 was
`7c9f1632984fdd857fbd26d15a72339980b1c2cbd3b3f9f7501e70f918b3b368`;
the converted annotation SHA-256 was
`d9b983aefb6343abac4c2c0bf0fff7f01cc45a70100b3ba392216298f0c9f7d6`.
