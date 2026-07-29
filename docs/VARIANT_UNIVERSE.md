# Reference-derived MANE variant universe

Production inputs are generated from the pinned GRCh38 FASTA and MANE Select
v1.5 annotation. The 2019 precomputed SpliceAI VCFs are not used as input.
This prevents their coordinates, alleles, gene annotations, or existing
`SpliceAI` INFO values from entering the new resource.

## Scope

Eligible anchors are A, C, G, or T bases in the union of the half-open
transcript spans in the converted MANE Select v1.5 annotation. Overlapping
transcripts are merged, so a genomic variant is emitted once; the scorer can
still return multiple gene annotations at overlapping loci.

At each eligible anchor, the generated records are:

- SNV: the three non-reference single-nucleotide alleles.
- Indel: four single-base insertions (`REF` plus A, C, G, or T) and deletions
  of 1, 2, 3, or 4 following reference bases, represented with the VCF anchor.

This bounded indel definition reproduces the variant classes in Illumina's
2019 precomputed indel resource: four insertions and four deletions per
eligible position. It does not claim to cover arbitrary-length indels, which
would be an unbounded variant space. Records involving ambiguous reference
bases are not emitted.

The generator intentionally does not add a `SpliceAI` INFO header or value.

## Plan

Create separate immutable SNV and indel plans with approximately one million
records per shard:

```bash
spliceai-batched-universe plan \
  --annotation MANE.GRCh38.v1.5.primary.spliceai.txt \
  --annotation-release 1.5 \
  --annotation-sha256 e323dddd489bcde6b5016776ccb1dd6955bb62c5af576c120f7b9815be2bdd53 \
  --reference genome.fa \
  --reference-sha256 d2b7be348fb20af46461855faec64dfbd21532620bd125783df050180446055e \
  --target-records 1000000 \
  --kind snv \
  --output snv.plan.tsv

spliceai-batched-universe plan \
  --annotation MANE.GRCh38.v1.5.primary.spliceai.txt \
  --annotation-release 1.5 \
  --annotation-sha256 e323dddd489bcde6b5016776ccb1dd6955bb62c5af576c120f7b9815be2bdd53 \
  --reference genome.fa \
  --reference-sha256 d2b7be348fb20af46461855faec64dfbd21532620bd125783df050180446055e \
  --target-records 1000000 \
  --kind indel \
  --output indel.plan.tsv
```

The plan records the exact reference and annotation checksums, merged MANE
span size, genomic regions, variant class, and estimated record count for each
task. Shards never mix contigs and are emitted in reference coordinate order.
Any supplied checksum is verified against the asset while the plan is created;
it is not accepted as an unverified label.
Each region retains both the annotation contig name (for example `1`) and its
resolved FASTA contig (for example `chr1`). Generated VCF records use the
annotation name required by SpliceAI's transcript lookup, while their
reference alleles are fetched from the resolved FASTA contig.

## Generate

Submit the CPU preprocessing array:

```bash
export UNIVERSE_PLAN=/absolute/path/universe.plan.tsv
export UNIVERSE_DIR=/absolute/path/universe
export REFERENCE=/absolute/path/genome.fa
export MAX_CONCURRENT=16

scripts/slurm/submit_universe.sh
```

Submit the SNV and indel plans separately. If a plan is larger than the
site's permitted Slurm array size, set `ARRAY_START` and `ARRAY_END` and submit
it in non-overlapping ranges. The same variables are supported by the GPU
array submitter.

Each task writes an indexed BGZF VCF, its SHA-256 checksum, actual record
count, and an atomic completion marker. The marker also records the generator
SHA-256 and compression-thread count. A completed shard is reused only when
its output checksum, plan, generator, and compression configuration still
match. The submitter verifies the reference checksum once and passes that
verified digest to every array task, avoiding a full FASTA rehash in each
task.

After every generation task succeeds, create the three-column scoring manifest:

```bash
spliceai-batched-universe finalize \
  --plan "${UNIVERSE_PLAN}" \
  --input-dir "${UNIVERSE_DIR}" \
  --output "${UNIVERSE_DIR}/scoring-manifest.tsv" \
  --verify-checksums
```

The resulting manifest is accepted directly by `scripts/slurm/submit_array.sh`.
Run one SNV and one indel shard first to measure actual generation speed,
compressed input size, output expansion, node-local scratch use, and
end-to-end A100 throughput before submitting the full arrays.
