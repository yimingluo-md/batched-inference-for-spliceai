# Validation source provenance

The 2026-07-28 validation artifacts retain the exact commit identifiers used
on the compute system:

- optimized validation: `6c279a5fe16d1a64f593cf54003ba028d6bc3a83`;
- optimized official-comparison run:
  `b1068905be6cde7b8e59e291af119c62804a6626`; and
- official wrapper: `2b6b4ced3bcfadfaa717d10c33ab1678aa19d6da`.

Those identifiers are intentionally not rewritten. The public repository was
later re-rooted to remove earlier release-candidate history with incompatible
temporary licensing language. The original Git objects are retained in a
private recovery/audit bundle.

The scoring paths in the public source are semantically identical to those
used for the recorded runs. The following SHA-256 values are over Python
abstract-syntax-tree dumps produced with Python 3.9
(`ast.dump(ast.parse(source), include_attributes=False)`):

| Validation source | File | Validation AST SHA-256 | Public-source AST SHA-256 |
| --- | --- | --- | --- |
| `6c279a5` / `b106890` | `cli.py` | `5527aec5d1b49ca668920e753540ffa06b0c3ea382d77de51054af3a9bbfc0df` | `5527aec5d1b49ca668920e753540ffa06b0c3ea382d77de51054af3a9bbfc0df` |
| `6c279a5` / `b106890` | `scoring.py` | `00700222bbb3a15b675faa0ade7e82505a9e6887ab5826d106920a5d19c26468` | `00700222bbb3a15b675faa0ade7e82505a9e6887ab5826d106920a5d19c26468` |
| `6c279a5` / `b106890` | `tensorflow_policy.py` | `a4b993308c676037cd02208615f6dd02fc1dc62d50c9d18acdfcf7d08133f16c` | `a4b993308c676037cd02208615f6dd02fc1dc62d50c9d18acdfcf7d08133f16c` |
| `b106890` | `broad.py` | `4cd871c53be85199b5dc65a7a7eea27b44ede396386671056df23a57b6971fda` | `4cd871c53be85199b5dc65a7a7eea27b44ede396386671056df23a57b6971fda` |
| `b106890` | `runtime_manifest.py` | `b3d1761b2060b88f258fba6f03ea9885f9b0e6d873ec01a823ac12b4ebf1b459` | `b3d1761b2060b88f258fba6f03ea9885f9b0e6d873ec01a823ac12b4ebf1b459` |
| `2b6b4ce` | `official.py` | `38092c96ea4ee623e71b140f64a538828200b1c975a2b3ecc3df55d5fc888672` | `38092c96ea4ee623e71b140f64a538828200b1c975a2b3ecc3df55d5fc888672` |

Some byte-level hashes differ only because the source was subsequently
formatted. The public source at commit
`a145b3c6aeee8fe020033a8a6a0e71816772e73a` was subsequently exercised in the
2026-08-20 SNV production canary. Its generator recreated the 999,999-record
input byte-for-byte, and its scorer recreated the prior million-record output
byte-for-byte at batch 1024. The indel production canary remains pending.
