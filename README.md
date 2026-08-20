# Batched inference for SpliceAI

> **SNV production canary passed; indel production pilot pending**

Batched inference for SpliceAI is a high-throughput VCF runner for a
**separately installed** SpliceAI 1.3.1 runtime. It keeps the five-model
ensemble and VCF score format while reducing repeated work through
cross-variant batching and reuse of reference predictions at the same locus
and transcript.

This is an independent research project. It is not affiliated with or endorsed
by Illumina.

## Motivation

Illumina's 2019 GRCh38 precomputed SpliceAI scores enable efficient annotation
but were generated using an older transcript set and include errors introduced
by transcript selection and genome-build liftover. [Martin-Geary et
al.](https://doi.org/10.1101/2025.08.27.25334471) reported that these issues
affect 8.34% of theoretical SNVs and SpliceAI accuracy in 34.98% of evaluated
disease-associated genes, potentially causing clinically relevant
splice-altering variants to be missed. The [Broad SpliceAI
Lookup](https://spliceailookup.broadinstitute.org/) addresses several
limitations by recomputing scores with updated annotations and supporting
masked predictions with a 500-nt maximum distance, but its public service is
intentionally limited to a few queries per user per minute and therefore cannot
support genome-wide annotation. Ensembl provides updated MANE v1.4-based GRCh38
scores, but [only for
SNVs](https://www.ensembl.org/info/docs/tools/vep/script/vep_plugins.html);
indel annotation still relies on the older Illumina resource. Increasing the
maximum distance from 50 to 500 nt broadens the region in which SpliceAI can
report predicted splice-site changes and may improve sensitivity to clinically
relevant distal events ([Pitsava et
al.](https://doi.org/10.1016/j.gim.2025.101574)). This project therefore
enables reproducible, high-throughput generation of masked (`M=1`), `D=500`
SpliceAI scores for all SNVs and small indels using current MANE Select v1.5
transcripts.

## Status

- Implementation: upstream-compatibility and orchestration corrections applied
- Current scoring-engine scientific validation: passed
- Validated SNV-production A100 batch size: 1024
- Current 50,000-record deterministic repeat test: byte-identical
- Historical 4,000-record batch-128 versus batch-256 comparison: exact
- Current 50,000-record stratified optimized validation: passed
- Current 20,000-record comparison with the official CLI: exact
- Current production annotation: MANE Select v1.5, checksum pinned
- Current MANE v1.5 versus Broad Lookup API: 64/64 exact
- Current Slurm scoring completion/restart smoke test: passed
- Reference-derived SNV universe: 999,999-record production canary passed
- Current SNV production output: byte-identical to the prior million-record pilot
- Reference-derived indel universe: production pilot pending
- License: GPL-3.0-or-later
- Current-tree licensing and provenance audit: passed

The current validation uses deterministic TensorFlow/cuDNN settings with TF32
disabled. It includes 50,000 optimized records, an exact 20,000-record
official-CLI comparison, byte-identical repeat outputs, and 64 exact external
Broad Lookup API comparisons. The current public source also passed a
999,999-record SNV production canary at batch 1024, including exact agreement
with the deterministic official comparator on 10,000 stratified SNVs,
byte-identical agreement with the prior million-record pilot, indexed-output
and record-count gates, and restart skipping. SNV production is ready for a
staged launch; the indel production pilot remains pending.

See [VALIDATION.md](docs/VALIDATION.md), [BENCHMARKS.md](docs/BENCHMARKS.md),
[the validation report](validation/VALIDATION_REPORT.md), and
[the licensing provenance review](docs/LICENSE_REVIEW.md).

## Why it is faster

1. Many sequences are passed to each model invocation.
2. The reference prediction is computed once for alternate alleles at the same
   locus/transcript.
3. Indels are grouped by encoded sequence length.
4. VCF processing is streamed in bounded chunks.
5. HPC jobs operate on restartable, indexed shards.

## Requirements

- Linux with an NVIDIA GPU
- A separately installed SpliceAI 1.3.1 runtime
- TensorFlow compatible with that SpliceAI installation
- Python 3.7+ (3.9+ recommended outside legacy containers)
- `numpy`, `pysam`, `bcftools`, `bgzip`, and `tabix`
- Reference FASTA with `.fai`
- `grch37`, `grch38`, or a SpliceAI-compatible custom annotation file

SpliceAI and its model files are intentionally not bundled.
Both the optimized runner and the supplied official-CLI wrapper configure
deterministic TensorFlow/cuDNN execution, disable cuDNN autotuning, and disable
TF32 before TensorFlow loads so A100 comparisons use the same numerical
policy.

## Installation

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
```

Install SpliceAI independently. This project targets the GPL-era SpliceAI
1.3.1 release; see [LICENSE_REVIEW.md](docs/LICENSE_REVIEW.md).

## Basic use

```bash
spliceai-batched \
  -I input.vcf.gz \
  -O output.vcf.gz \
  -R genome.fa \
  -A grch38 \
  -D 500 \
  -M 1 \
  --batch-size 256 \
  --chunk-records 4096

tabix -p vcf output.vcf.gz
```

For the scientific production run, replace `grch38` with the path to the
validated MANE Select v1.5 SpliceAI annotation.
The validated SNV production configuration uses `--batch-size 1024` and
`--chunk-records 16384` on an A100 80 GB GPU.

Generate that annotation from the official NCBI Ensembl GTF:

```bash
spliceai-batched-mane \
  --input MANE.GRCh38.v1.5.ensembl_genomic.gtf.gz \
  --output MANE.GRCh38.v1.5.primary.spliceai.txt
```

By default, the converter retains chromosomes 1–22, X, and Y and excludes
MANE records located only on GRCh38 patch/alternate contigs, matching the
primary-assembly FASTA used for production. Use `--include-nonprimary` only
with a reference FASTA containing those contigs.

Do not commit the downloaded annotation; record its source URL and SHA-256
checksums in the run manifest.

## Generate clean production inputs

For a full MANE resource, generate variants directly from the pinned GRCh38
FASTA and the union of MANE Select v1.5 transcript spans. Do not use an older
precomputed score VCF as input.

```bash
spliceai-batched-universe plan \
  --annotation MANE.GRCh38.v1.5.primary.spliceai.txt \
  --annotation-release 1.5 \
  --reference genome.fa \
  --target-records 1000000 \
  --kind snv \
  --output snv.plan.tsv
```

The defined SNV universe contains all three non-reference alleles at each
eligible base. The bounded indel universe mirrors the 2019 precomputed
resource: four single-base insertions and deletions of 1–4 bases per eligible
anchor. Create the indel plan with `--kind indel`; keeping the two classes in
separate plans makes large Slurm arrays easier to stage. Generated VCFs contain
no inherited `SpliceAI` annotation.

See [VARIANT_UNIVERSE.md](docs/VARIANT_UNIVERSE.md) for the exact definition,
parallel generation workflow, completion checks, and scoring-manifest command.

## Validation

Create a deterministic stratified sample:

```bash
spliceai-batched-sample \
  --input resource.vcf.gz \
  --annotation grch38.txt \
  --output stratified.vcf \
  --target-records 25000
```

Compare optimized and official outputs:

```bash
spliceai-batched-official \
  -I sample.vcf \
  -O official.vcf \
  -R genome.fa \
  -A annotation.txt \
  -D 500 \
  -M 1

spliceai-batched-compare \
  official.vcf optimized.vcf \
  --json comparison.json \
  --details-dir comparison-details
```

The comparison command fails when record identities differ, annotation entries
are missing, or the maximum formatted score difference exceeds 0.011.

For a rate-limited external check, the
`spliceai-batched-broad` command compares local fields with Broad's MANE Select
API response and caches every response locally. Raw third-party API responses
are intentionally excluded from this repository; only the query manifest and
comparison evidence are retained. See the exact command and evidence in
`docs/VALIDATION.md`. The command fails closed if any requested row cannot be
numerically compared; unsupported placeholder annotations must not be counted
as successful comparisons.

## Research-use notice

This software is research software, not a validated clinical diagnostic
device. Predictions require independent review and must not be the sole basis
for patient-care decisions.

## AI-assisted development disclosure

This project was developed with assistance from OpenAI Codex (GPT-5.6 Sol)
and Anthropic Claude Code (Claude Opus 5). AI-generated suggestions were
reviewed and tested before inclusion. These tools are not project authors, and
their use does not imply endorsement by OpenAI or Anthropic.

## License and provenance

Batched inference for SpliceAI is a substantially modified work based on the
GPL-licensed SpliceAI 1.3.1 scoring implementation and is released under
GPL-3.0-or-later. Illumina relicensed later repository revisions under
PolyForm Strict in 2025; this project does not use those revisions.

The SpliceAI name is used only to identify compatibility with the upstream
software. This project is independent and does not use Illumina branding.
Model weights are not included and have separate terms. See
[LICENSE](LICENSE), [COPYRIGHT](COPYRIGHT), [NOTICE](NOTICE), and
[LICENSE_REVIEW.md](docs/LICENSE_REVIEW.md).

Contributions must include source/license provenance and a Developer
Certificate of Origin sign-off; see [CONTRIBUTING.md](CONTRIBUTING.md).
