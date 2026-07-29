# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import json
from pathlib import Path

import pysam
import pytest

from spliceai_batched import universe
from spliceai_batched.universe import (
    generate_task,
    merge_intervals,
    read_plan,
    write_plan,
    write_scoring_manifest,
)


def write_assets(tmp_path: Path) -> tuple[Path, Path]:
    reference = tmp_path / "genome.fa"
    reference.write_text(">chr1\nACGTACGT\n", encoding="utf-8")
    pysam.faidx(str(reference))
    annotation = tmp_path / "mane.txt"
    annotation.write_text(
        "#NAME\tCHROM\tSTRAND\tTX_START\tTX_END\tEXON_START\tEXON_END\n"
        "GENE1\t1\t+\t0\t3\t0,\t3,\n"
        "GENE2\t1\t-\t2\t4\t2,\t4,\n",
        encoding="utf-8",
    )
    return reference, annotation


def test_merge_intervals_combines_overlaps_and_adjacent() -> None:
    assert merge_intervals([(5, 8), (1, 3), (3, 5), (10, 12)]) == [
        (1, 8),
        (10, 12),
    ]


def test_plan_uses_union_of_transcript_spans(tmp_path: Path) -> None:
    reference, annotation = write_assets(tmp_path)
    plan = tmp_path / "universe.tsv"

    summary = write_plan(
        str(annotation),
        str(reference),
        str(plan),
        target_records=100,
        annotation_release="1.5",
    )
    metadata, rows = read_plan(str(plan))

    assert summary == {
        "merged_transcript_bases": 4,
        "snv_tasks": 1,
        "snv_estimated_records": 12,
        "indel_tasks": 1,
        "indel_estimated_records": 32,
        "tasks": 2,
    }
    assert metadata["annotation_release"] == "1.5"
    assert rows[0]["regions"] == [("1", "chr1", 0, 4)]
    assert rows[1]["regions"] == [("1", "chr1", 0, 4)]


def test_plan_rejects_incorrect_supplied_asset_checksum(tmp_path: Path) -> None:
    reference, annotation = write_assets(tmp_path)

    with pytest.raises(ValueError, match="Annotation checksum mismatch"):
        write_plan(
            str(annotation),
            str(reference),
            str(tmp_path / "universe.tsv"),
            annotation_sha256="0" * 64,
        )


def test_generate_clean_snv_and_legacy_bounded_indel_universe(
    tmp_path: Path,
) -> None:
    reference, annotation = write_assets(tmp_path)
    plan = tmp_path / "universe.tsv"
    shards = tmp_path / "shards"
    scoring_manifest = tmp_path / "score.tsv"
    write_plan(
        str(annotation),
        str(reference),
        str(plan),
        target_records=100,
        annotation_release="1.5",
    )

    snv = generate_task(
        str(plan),
        1,
        str(shards),
        progress_every=0,
    )
    indel = generate_task(
        str(plan),
        2,
        str(shards),
        progress_every=0,
    )
    snv_repeat = generate_task(
        str(plan),
        1,
        str(shards),
        progress_every=0,
    )

    assert snv["records"] == 12
    assert indel["records"] == 32
    assert snv_repeat == snv
    with pysam.VariantFile(str(shards / "snv-000001.vcf.gz")) as handle:
        assert "SpliceAI" not in handle.header.info
        records = list(handle)
    assert records[0].chrom == "1"
    assert [
        (record.pos, record.ref, tuple(record.alts or ())) for record in records[:3]
    ] == [
        (1, "A", ("C",)),
        (1, "A", ("G",)),
        (1, "A", ("T",)),
    ]

    with pysam.VariantFile(str(shards / "indel-000001.vcf.gz")) as handle:
        records = list(handle)
    assert [
        (record.pos, record.ref, tuple(record.alts or ())) for record in records[:8]
    ] == [
        (1, "A", ("AA",)),
        (1, "A", ("AC",)),
        (1, "A", ("AG",)),
        (1, "A", ("AT",)),
        (1, "AC", ("A",)),
        (1, "ACG", ("A",)),
        (1, "ACGT", ("A",)),
        (1, "ACGTA", ("A",)),
    ]

    summary = write_scoring_manifest(
        str(plan),
        str(shards),
        str(scoring_manifest),
        verify_checksums=True,
    )
    assert summary == {
        "snv_shards": 1,
        "snv_records": 12,
        "indel_shards": 1,
        "indel_records": 32,
        "shards": 2,
        "records": 44,
    }
    assert len(scoring_manifest.read_text(encoding="utf-8").splitlines()) == 3


def test_generate_rejects_unverified_reference_override(tmp_path: Path) -> None:
    reference, annotation = write_assets(tmp_path)
    plan = tmp_path / "universe.tsv"
    write_plan(
        str(annotation),
        str(reference),
        str(plan),
        target_records=100,
        kinds=("snv",),
    )
    different_reference = tmp_path / "different.fa"
    different_reference.write_text(">chr1\nTCGTACGT\n", encoding="utf-8")
    pysam.faidx(str(different_reference))

    with pytest.raises(ValueError, match="Reference checksum mismatch"):
        generate_task(
            str(plan),
            1,
            str(tmp_path / "shards"),
            reference_path=str(different_reference),
            progress_every=0,
        )

    with pytest.raises(
        ValueError,
        match="Preverified reference checksum does not match",
    ):
        generate_task(
            str(plan),
            1,
            str(tmp_path / "shards"),
            reference_path=str(reference),
            reference_sha256="0" * 64,
            progress_every=0,
        )


def test_generate_cleans_partial_files_after_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference, annotation = write_assets(tmp_path)
    plan = tmp_path / "universe.tsv"
    shards = tmp_path / "shards"
    write_plan(
        str(annotation),
        str(reference),
        str(plan),
        target_records=100,
        kinds=("snv",),
    )

    def fail_write(*args: object, **kwargs: object) -> int:
        raise RuntimeError("injected failure")

    monkeypatch.setattr(universe, "write_records", fail_write)
    with pytest.raises(RuntimeError, match="injected failure"):
        generate_task(
            str(plan),
            1,
            str(shards),
            progress_every=0,
        )

    assert list(shards.glob("*.vcf.gz")) == []
    assert list(shards.glob(".*.partial.vcf.gz")) == []


def test_ambiguous_reference_bases_are_not_emitted(tmp_path: Path) -> None:
    reference = tmp_path / "genome.fa"
    reference.write_text(">1\nACNTACGT\n", encoding="utf-8")
    pysam.faidx(str(reference))
    annotation = tmp_path / "mane.txt"
    annotation.write_text(
        "#NAME\tCHROM\tSTRAND\tTX_START\tTX_END\tEXON_START\tEXON_END\n"
        "GENE\t1\t+\t0\t4\t0,\t4,\n",
        encoding="utf-8",
    )
    plan = tmp_path / "universe.tsv"
    shards = tmp_path / "shards"
    write_plan(
        str(annotation),
        str(reference),
        str(plan),
        target_records=100,
        kinds=("snv",),
    )

    result = generate_task(
        str(plan),
        1,
        str(shards),
        progress_every=0,
    )

    assert result["records"] == 9


def test_finalize_rejects_shard_from_stale_generator(tmp_path: Path) -> None:
    reference, annotation = write_assets(tmp_path)
    plan = tmp_path / "universe.tsv"
    shards = tmp_path / "shards"
    scoring_manifest = tmp_path / "score.tsv"
    write_plan(
        str(annotation),
        str(reference),
        str(plan),
        target_records=100,
        kinds=("snv",),
    )
    generate_task(
        str(plan),
        1,
        str(shards),
        progress_every=0,
    )
    completion_path = shards / "snv-000001.complete.json"
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    completion["generator_sha256"] = "0" * 64
    completion_path.write_text(
        json.dumps(completion) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Inconsistent universe shard"):
        write_scoring_manifest(
            str(plan),
            str(shards),
            str(scoring_manifest),
            verify_checksums=True,
        )

    assert not scoring_manifest.exists()


def test_finalize_failure_preserves_existing_manifest_atomically(
    tmp_path: Path,
) -> None:
    reference, annotation = write_assets(tmp_path)
    plan = tmp_path / "universe.tsv"
    shards = tmp_path / "shards"
    scoring_manifest = tmp_path / "score.tsv"
    write_plan(
        str(annotation),
        str(reference),
        str(plan),
        target_records=8,
        kinds=("snv",),
    )
    _, rows = read_plan(str(plan))
    assert len(rows) == 2
    generate_task(
        str(plan),
        1,
        str(shards),
        progress_every=0,
    )
    previous = "# existing complete manifest\n"
    scoring_manifest.write_text(previous, encoding="utf-8")

    with pytest.raises(ValueError, match="Incomplete universe shard"):
        write_scoring_manifest(
            str(plan),
            str(shards),
            str(scoring_manifest),
            verify_checksums=True,
        )

    assert scoring_manifest.read_text(encoding="utf-8") == previous
    assert list(tmp_path.glob(f".{scoring_manifest.name}.*.partial")) == []
