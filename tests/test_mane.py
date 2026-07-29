# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

from spliceai_batched.mane import attributes, convert


def test_attributes_preserve_repeated_tags() -> None:
    parsed = attributes('gene_name "GENE"; tag "basic"; tag "MANE_Select";')
    assert parsed["tag"] == ["basic", "MANE_Select"]


def test_convert_coordinates_and_exon_order(tmp_path: Path) -> None:
    source = tmp_path / "mane.gtf"
    output = tmp_path / "mane.txt"
    source.write_text(
        "chr2\tsrc\ttranscript\t101\t400\t.\t-\t.\t"
        'gene_name "GENE"; transcript_id "TX1"; tag "MANE_Select";\n'
        "chr2\tsrc\texon\t301\t400\t.\t-\t.\t"
        'gene_name "GENE"; transcript_id "TX1"; tag "MANE_Select";\n'
        "chr2\tsrc\texon\t101\t200\t.\t-\t.\t"
        'gene_name "GENE"; transcript_id "TX1"; tag "MANE_Select";\n',
        encoding="utf-8",
    )

    summary = convert(str(source), str(output))
    assert summary == {"transcripts": 1, "genes": 1, "contigs": 1, "exons": 2}
    assert output.read_text(encoding="utf-8").splitlines()[1] == (
        "GENE\t2\t-\t100\t400\t100,300,\t200,400,"
    )


def test_nonprimary_contigs_are_excluded_by_default(tmp_path: Path) -> None:
    source = tmp_path / "mane.gtf"
    primary_output = tmp_path / "primary.txt"
    all_output = tmp_path / "all.txt"
    source.write_text(
        "chr1_KN196472v1_fix\tsrc\ttranscript\t101\t200\t.\t+\t.\t"
        'gene_name "PATCH"; transcript_id "TX2"; tag "MANE_Select";\n'
        "chr1_KN196472v1_fix\tsrc\texon\t101\t200\t.\t+\t.\t"
        'gene_name "PATCH"; transcript_id "TX2"; tag "MANE_Select";\n',
        encoding="utf-8",
    )

    primary = convert(str(source), str(primary_output))
    all_contigs = convert(str(source), str(all_output), include_nonprimary=True)

    assert primary["transcripts"] == 0
    assert primary_output.read_text(encoding="utf-8").count("\n") == 1
    assert all_contigs["transcripts"] == 1
    assert "\t1_KN196472v1_fix\t" in all_output.read_text(encoding="utf-8")
