# Descriptive analysis of the released SNV resource

This package contains the code and sanitized results used to characterize the
3,408,398,835 single-nucleotide variants (SNVs) in the MANE Select v1.5,
GRCh38, D=500, masked SpliceAI release. It does not retrain or rerun SpliceAI.
The source dataset remains available on
[Hugging Face](https://huggingface.co/datasets/luoyiming1991/spliceai-mane-v1.5-d500-m1-snv).

## Definitions

The variant-level maximum is the largest of the four displayed delta scores
across every gene annotation on one Variant Call Format (VCF) record.
Variant–gene annotations are counted separately. Multiple distinct gene
symbols define a multi-gene variant; duplicate symbols within a record fail
the audit. A distal event is a positive displayed delta score whose associated
absolute position is greater than 50 nucleotides. Thresholds apply to each
distal score itself. Variants are counted once per threshold; gene-specific
event fields need not be unique splice-site positions. Both 0.00 and -0.00
are treated as zero. These are descriptive counts of published two-decimal
scores, not a D=50 rerun or a measure of clinical sensitivity.

## Reproduce score summaries

From this directory, Python 3 and its standard library suffice to recompute
the summaries from the 24 included chromosome results:

```bash
python3 aggregate_score_audit.py --results results/chromosomes --manifest results/release-manifest.json --output recomputed
python3 test_aggregate_score_audit.py
```

To independently rescan downloaded release VCFs, use a C++17 compiler and zlib:

```bash
g++ -std=c++17 -O3 -Wall -Wextra score_audit.cpp -lz -o score_audit
python3 test_score_audit.py ./score_audit
python3 run_score_audit.py --release RELEASE_DIRECTORY --output NEW_RESULTS --contig 1
```

Repeat for chromosomes 1–22, X, and Y, then aggregate as above. The wrapper
requires the release's metadata/release-manifest.json and verifies each file's
SHA-256 checksum, size, and record count. The C++ scanner checks record order,
SNV alleles, annotation structure, unique gene symbols, score bounds, and
delta-position bounds. The optional scheduler wrapper requests no GPUs.

The independent Python counter test uses 1,000 seeded synthetic records and
malformed-input tests. It also accepts existing VCF samples as additional
arguments. The same counters previously matched all 120 retained external
validation records.

## Reproduce production time summaries

```bash
python3 verify_runtime.py
```

Public per-job records allow recomputation of accepted scoring time and all
scoped GPU allocation totals. Allocated GPU-hours are not hardware utilization.
Only the 3,449 accepted scoring jobs contribute records to the final release;
they represent 3,417 full shards and 32 parts reconstructing two parents.
Production retries and the separate chunk-size control are identified by scope.
Pilot runs, earlier validation, and CPU-only preparation/packaging are excluded.

## Provenance and privacy

The scan covers every released VCF record, not a sample. The original analysis
source and input-file hashes are retained. Public chromosome files omit
scheduler identifiers; their result hashes consequently differ from the private
originals, and the included aggregate was regenerated from these public files.
All numerical counters were verified unchanged. Runtime records similarly
omit scheduler identifiers and raw operational logs. Hashes of the retained
private source evidence support provenance but do not imply those private
files are downloadable. No personal filesystem paths or credentials are
included. The manuscript and author correspondence are not part of this package.

## Licensing

Analysis code is covered by the repository's GPL-3.0-or-later license.
Score-derived result files in results/ retain the dataset's CC BY-NC 4.0
attribution context, including credit to Illumina for SpliceAI and its trained
models. See the [dataset license and attribution notices](https://huggingface.co/datasets/luoyiming1991/spliceai-mane-v1.5-d500-m1-snv).
