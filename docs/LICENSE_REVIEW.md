# Licensing and provenance audit

Audit date: 2026-07-29

This is a technical provenance record, not legal advice. It distinguishes the
source repository from separately obtained model weights, reference data, API
responses, containers, and generated score resources.

## Conclusion

The source tree can be distributed under `GPL-3.0-or-later`. Its adapted
scoring logic is anchored to Illumina SpliceAI v1.3.1, which was released under
GPLv3-or-later. The repository does not contain model weights or other
restricted runtime assets.

This conclusion does **not** clear the SpliceAI model weights or a generated
genome-wide score database for unrestricted redistribution. Those require a
separate review of the terms accompanying the weights and outputs.

## Controlling upstream source release

The only SpliceAI source release used as the adaptation baseline is:

- release: `v1.3.1`, 2020-03-07;
- tag commit: `b3c7f17b4137cb32b30c56c064f8b90b9b8f38d0`;
- tag `LICENSE`: “SpliceAI source code is provided under the GPLv3
  license”;
- tag `COPYRIGHT`: GNU GPL version 3 or, at the recipient's option, any
  later version;
- PyPI source archive SHA-256:
  `65c76b012ffd2ca97ca96d7f4c0897c78b9aba4d4ca4068331f7fb5cd5c3b7e1`.

Primary evidence:

- https://github.com/Illumina/SpliceAI/tree/v1.3.1
- https://github.com/Illumina/SpliceAI/blob/v1.3.1/LICENSE
- https://github.com/Illumina/SpliceAI/blob/v1.3.1/COPYRIGHT
- https://pypi.org/project/spliceai/1.3.1/

The repository's `cli.py` and `scoring.py` identify the adapted origin,
Illumina copyright, modification year, and project notice. The complete work
is licensed under GPL-3.0-or-later, the full GPLv3 text is supplied without a
project-specific preamble, and corresponding source is present.

## Later Illumina revisions are excluded

Illumina changed the license on the repository's then-current branch to
PolyForm Strict on 2025-07-18:

- commit:
  https://github.com/Illumina/SpliceAI/commit/fef2d058c46847a170c39813fc1637cfd2a91a47
- current license:
  https://github.com/Illumina/SpliceAI/blob/master/LICENSE

That later change does not revoke the already granted v1.3.1 GPL license, but
post-v1.3.1 Illumina code is outside this project's provenance. Maintainers
must not copy or cherry-pick later Illumina revisions without a new license
review.

## Other SpliceAI forks examined

The Broad/TGG `bw2/SpliceAI` fork and its `get_all_scores` work were examined
as comparison implementations. They are not the source baseline for this
repository, and no post-v1.3.1 Broad source is included here. In particular,
this repository does not include the fork's raw-score or inserted-base output
extensions.

If a future change copies from that fork, its exact commit and author must be
recorded and its GPL notices preserved:

- https://github.com/bw2/SpliceAI

## Modification scope

Relative to SpliceAI v1.3.1, this project adds or substantially changes:

- batched five-model inference;
- reference-prediction reuse;
- length-grouped indel inference;
- bounded VCF streaming;
- deterministic TensorFlow/cuDNN controls and TF32 policy;
- corrected minus-strand output orientation;
- comparison, sampling, MANE-conversion, and runtime-manifest tools;
- reference-derived variant-universe generation; and
- restartable, fingerprinted Slurm orchestration.

The runtime imports a separately installed `spliceai` package. Importing it
does not place that package, its annotations, or its model files in this source
distribution.

## Repository inventory

Included:

- project source, tests, scripts, and documentation;
- synthetic unit-test fixtures;
- checksums, query manifests, and comparison summaries; and
- small, sanitized validation metadata.

Not included:

- SpliceAI or other model weights;
- the SpliceAI package;
- deployment containers;
- reference genomes;
- MANE or GENCODE annotation datasets;
- source or full production VCFs; or
- raw Broad Lookup API response caches.

The tracked-file and history audit found no model files, reference assets,
containers, patient-derived variants, credentials, or private keys in the
clean public history.

## Models, annotations, and generated outputs

Illumina's current repository describes the trained model terms as
CC BY-NC 4.0. The v1.3.1 package and current repositories should be consulted
for the exact terms accompanying the particular copy obtained by a user:

- https://github.com/Illumina/SpliceAI/blob/master/spliceai/models/LICENSE

The weights are deliberately neither vendored nor declared as an automatically
downloaded dependency. A container or binary distribution that includes them
needs a separate license analysis and attribution.

The terms for a complete public database of newly generated SpliceAI scores
are not explicit enough to infer unrestricted redistribution from this source
license. Do not publish the planned all-variant score VCFs under the project's
GPL license without written clarification from the relevant rights holder or
qualified legal review. Commercial use of CC BY-NC-licensed weights likewise
requires separate permission.

MANE/GENCODE and reference assets are not redistributed. Only source URLs,
release identifiers, and cryptographic hashes are recorded.

## Broad Lookup validation evidence

The validator sends sequential, rate-limited requests to the Broad Institute
SpliceAI Lookup API and uses the responses as an external scientific
comparison:

- service/repository: https://github.com/broadinstitute/SpliceAI-lookup
- service code license: MIT

The MIT license covers the service code but does not expressly state a license
for API output data. Therefore raw response JSON files are excluded from the
public tree and ignored by Git. The repository retains the 64-variant query
manifest and comparison summary, identifies the endpoint and parameters, and
makes no GPL or ownership claim over third-party model scores.

## Direct dependencies

Dependencies are resolved and installed separately; none is vendored. Each
retains its own license and bundled third-party notices.

| Component | Role | Upstream license record |
| --- | --- | --- |
| NumPy | runtime | BSD-3-Clause; https://github.com/numpy/numpy/blob/main/LICENSE.txt |
| pysam | runtime | MIT, with bundled component notices; https://github.com/pysam-developers/pysam/blob/master/COPYING |
| TensorFlow | external SpliceAI runtime | Apache-2.0; https://github.com/tensorflow/tensorflow/blob/master/LICENSE |
| pytest | tests only | MIT; https://github.com/pytest-dev/pytest/blob/main/LICENSE |
| setuptools | build only | MIT; https://github.com/pypa/setuptools/blob/main/LICENSE |
| wheel | build only | MIT; https://github.com/pypa/wheel/blob/main/LICENSE.txt |

Downstream binary or container distributors must inventory the exact resolved
versions and reproduce any notices required by those distributions.

## Naming and clinical-use boundary

“Batched inference for SpliceAI” is descriptive compatibility language. The
repository disclaims affiliation and endorsement and does not use Illumina
logos or trade dress. No trademark license is asserted.

The software is research software, not a validated clinical diagnostic device.
The source license does not establish clinical validity, regulatory clearance,
or fitness for patient-care decisions.

## History remediation

Early private release-candidate snapshots used temporary
no-redistribution language while provenance was being investigated. That
language was incompatible with distributing a work derived from GPL code.
`NOTICE` affirmatively withdraws that restriction for project source in those
former snapshots, limited to copyright held by Yiming Luo.
Obsolete tags and branches were removed, and the public repository was
re-rooted at the fully GPL-licensed, provenance-audited source tree. A private
local bundle preserves the former history for recovery and audit purposes.

## Release checklist result

- v1.3.1 commit and source-archive hash pinned: passed
- current versus historical Illumina license boundary documented: passed
- adapted files and modification date identified: passed
- full GPLv3 text and upstream copyright retained: passed
- model/reference/annotation/container assets absent: passed
- raw Broad API responses absent: passed
- direct dependencies inventoried and not vendored: passed
- clean-history credential and restricted-artifact scan: passed

Subject to the separate model/output cautions above, the source repository is
prepared for public distribution.
