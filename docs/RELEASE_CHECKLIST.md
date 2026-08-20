# Release checklist

## Scientific validation

- [x] Repeat the 50,000-record stratified optimized run on the corrected code
- [x] Repeat the 20,000-record official CLI comparison on the corrected code
- [x] All 24 primary chromosomes represented
- [x] Both transcript strands represented
- [x] SNVs, insertions, and deletions represented
- [x] Confirm annotation entry sets are identical on the corrected code
- [x] Confirm maximum score difference is at most 0.01
- [x] Review position differences on the corrected code (none found)
- [x] Confirm repeat SNV and indel outputs are byte-identical
- [x] Current MANE Select v1.5 primary annotation converted and checksum pinned
- [x] Patch/alternate-only MANE transcripts explicitly excluded and counted
- [x] Compare 64 balanced variants with the Broad Lookup API
- [x] Compare batch-1024 SNVs with 10,000 deterministic official outputs
- [x] Complete the 999,999-record current-source SNV production canary

## Engineering

- [x] No hard-coded username or project path in release scripts
- [x] Bounded-memory chunking
- [x] Restartable shards and completion markers
- [x] BGZF and tabix validation
- [x] Record-count gate
- [x] Smoke-test the corrected array submitter and restart skip on Slurm
- [x] Unit and integration tests pass in clean environment
- [x] Historical validation container SHA-256 recorded
- [x] Container SHA-256 enforced by shard restart fingerprints
- [x] Current revalidation container/runtime digest recorded
- [x] Model and annotation hashes recorded
- [x] Reference FASTA hash recorded
- [x] TF32 disabled in optimized and official-comparison entry points
- [x] TensorFlow/cuDNN determinism controls aligned across both entry points
- [x] Broad validation fails if any requested row is not compared
- [x] Current runtime manifest confirms `tf32_enabled=false`
- [x] Secret scan passes
- [x] Verify million-record SNV BGZF, tabix, counts, checksum, and restart skip

## Documentation

- [x] Installation and usage
- [x] Benchmark methods
- [x] Validation protocol
- [x] Security/data-handling policy
- [x] Citation metadata
- [x] Final validation report
- [x] Release notes

## License and provenance

- [x] Exact SpliceAI 1.3.1 GPL-era provenance recorded
- [x] Full GPLv3 text included
- [x] Repository licensed GPL-3.0-or-later
- [x] Illumina copyright and attribution preserved
- [x] Modified-work status and dates stated prominently
- [x] No upstream model weights included
- [x] No controlled or patient data included

## Publication

- [x] Public GitHub repository created
- [x] Tagged release candidate created
- [ ] Zenodo integration enabled
- [ ] DOI minted
- [ ] Release archived with checksums
