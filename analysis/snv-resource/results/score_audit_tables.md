# Full-release score audit

All 3,408,398,835 SNV records in 24 chromosome VCFs were scanned. All compressed VCF checksums and chromosome record counts matched the release manifest. This was not an independent reference-span reconciliation.

## Score distribution

Scores are the values stored in the released VCFs, rounded to two decimals. Variant-level maxima include all gene annotations.

| Maximum score | SNV records | % of SNVs | Variant–gene annotations | % of annotations |
|---|---:|---:|---:|---:|
| 0.00 | 2,961,647,015 | 86.8926% | 2,989,443,600 | 86.9340% |
| 0.01–0.19 | 430,092,084 | 12.6186% | 432,599,346 | 12.5801% |
| 0.20–0.49 | 10,654,221 | 0.3126% | 10,691,168 | 0.3109% |
| 0.50–0.79 | 2,678,400 | 0.0786% | 2,685,399 | 0.0781% |
| 0.80–1.00 | 3,327,115 | 0.0976% | 3,332,158 | 0.0969% |

## Annotation multiplicity

There were 3,438,751,671 variant–gene annotations and 19,299 distinct gene symbols. 16,221,258 SNVs (0.4759%) had annotations for multiple genes.

| Distinct genes per SNV | SNV records | % of SNVs |
|---|---:|---:|
| 1 | 3,392,177,577 | 99.5241% |
| 2 | 14,706,819 | 0.4315% |
| 3 | 135,768 | 0.0040% |
| 4 | 91,368 | 0.0027% |
| 5 | 94,011 | 0.0028% |
| 6 | 48,918 | 0.0014% |
| 7 | 69,912 | 0.0021% |
| 8 | 126,216 | 0.0037% |
| 9 | 88,191 | 0.0026% |
| 10 | 54,048 | 0.0016% |
| 11 | 33,858 | 0.0010% |
| 12 | 36,390 | 0.0011% |
| 13 | 147,018 | 0.0043% |
| 14 | 136,260 | 0.0040% |
| 15 | 152,514 | 0.0045% |
| 16 | 14,070 | 0.0004% |
| 17 | 10,122 | 0.0003% |
| 18 | 28,368 | 0.0008% |
| 19 | 136,377 | 0.0040% |
| 20 | 27,192 | 0.0008% |
| 21 | 12,153 | 0.0004% |
| 22 | 71,685 | 0.0021% |

## Reported distal effects

Distal means absolute reported position >50 nt and a positive displayed score. Thresholds apply to the distal score itself. Events are gene-specific AG/AL/DG/DL maxima and may refer to the same genomic position.

| Score threshold | SNVs with any qualifying score | SNVs with a qualifying distal event | % of all SNVs | % of score-qualified SNVs | Variant–gene entries with a qualifying distal event | Gene-specific distal event fields |
|---|---:|---:|---:|---:|---:|---:|
| ≥0.01 | 446,751,820 | 318,912,897 | 9.3567% | 71.3848% | 320,675,018 | 364,036,251 |
| ≥0.20 | 16,659,736 | 4,454,772 | 0.1307% | 26.7398% | 4,468,671 | 4,561,068 |
| ≥0.50 | 6,005,515 | 698,820 | 0.0205% | 11.6363% | 700,778 | 701,898 |
| ≥0.80 | 3,327,115 | 102,421 | 0.0030% | 3.0784% | 102,638 | 102,642 |

These descriptive counts do not establish which variants would be missed at D=50: the released D=500 maxima cannot reconstruct a D=50 calculation. A score of 0.00 may include a small unrounded prediction; its position is not counted as an effect.
The scan observed 14,558 score fields formatted as -0.00; these were counted as zero without modifying the VCFs.

## Distal event types

| Event type | Positive distal fields | Distal fields ≥0.20 | Distal fields ≥0.50 | Distal fields ≥0.80 |
|---|---:|---:|---:|---:|
| AG | 170,724,683 | 2,314,062 | 399,275 | 62,009 |
| AL | 11,723,995 | 117,843 | 8,190 | 950 |
| DG | 172,421,677 | 2,022,994 | 278,877 | 36,470 |
| DL | 9,165,896 | 106,169 | 15,556 | 3,213 |
