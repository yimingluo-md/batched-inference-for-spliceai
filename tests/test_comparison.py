# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from pathlib import Path

import pytest

from spliceai_batched.comparison import compare

HEADER = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
"""


def write_vcf(path: Path, annotations: list[str]) -> None:
    rows = []
    for index, annotation in enumerate(annotations, start=1):
        rows.append(f"1\t{100 + index}\t.\tA\tC\t.\t.\tSpliceAI={annotation}\n")
    path.write_text(HEADER + "".join(rows), encoding="utf-8")


def test_exact_multigene_comparison(tmp_path: Path) -> None:
    annotation = (
        "C|GENE1|0.10|0.20|0.30|0.40|1|2|3|4,C|GENE2|0.00|0.00|0.00|0.00|-1|-2|-3|-4"
    )
    baseline = tmp_path / "baseline.vcf"
    candidate = tmp_path / "candidate.vcf"
    write_vcf(baseline, [annotation])
    write_vcf(candidate, [annotation])

    result = compare(str(baseline), str(candidate))
    assert result.annotations_different == 0
    assert result.annotation_entries_missing == 0


def test_detects_score_and_position_differences(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.vcf"
    candidate = tmp_path / "candidate.vcf"
    write_vcf(baseline, ["C|GENE|0.10|0.20|0.30|0.40|1|2|3|4"])
    write_vcf(candidate, ["C|GENE|0.11|0.20|0.30|0.40|5|2|3|4"])

    result = compare(str(baseline), str(candidate))
    assert result.annotations_different == 1
    assert result.score_fields_different == 1
    assert result.max_score_difference == pytest.approx(0.01)
    assert result.position_fields_different == 1
    assert result.nontrivial_position_fields_different == 1


def test_zero_score_position_difference_is_trivial(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.vcf"
    candidate = tmp_path / "candidate.vcf"
    details = tmp_path / "details.tsv"
    write_vcf(baseline, ["C|GENE|0.00|0.00|0.00|0.00|1|2|3|4"])
    write_vcf(candidate, ["C|GENE|0.00|0.00|0.00|0.00|5|2|3|4"])

    result = compare(str(baseline), str(candidate), str(details))
    assert result.position_fields_different == 1
    assert result.nontrivial_position_fields_different == 0
    assert len(details.read_text(encoding="utf-8").splitlines()) == 2


def test_detects_missing_annotation_entry(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.vcf"
    candidate = tmp_path / "candidate.vcf"
    write_vcf(
        baseline,
        ["C|GENE1|0.10|0.20|0.30|0.40|1|2|3|4,C|GENE2|0.10|0.20|0.30|0.40|1|2|3|4"],
    )
    write_vcf(candidate, ["C|GENE1|0.10|0.20|0.30|0.40|1|2|3|4"])

    result = compare(str(baseline), str(candidate))
    assert result.annotation_entries_missing == 1


def test_malformed_vcf_row_has_contextual_error(tmp_path: Path) -> None:
    baseline = tmp_path / "malformed.vcf"
    candidate = tmp_path / "candidate.vcf"
    baseline.write_text(HEADER + "1\t100\t.\tA\tC\n", encoding="utf-8")
    write_vcf(candidate, ["C|GENE|0.10|0.20|0.30|0.40|1|2|3|4"])

    with pytest.raises(ValueError, match=r"malformed\.vcf:3: expected at least 8"):
        compare(str(baseline), str(candidate))
