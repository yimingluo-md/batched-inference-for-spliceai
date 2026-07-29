# SPDX-License-Identifier: GPL-3.0-or-later

import json
import sys
from pathlib import Path

import pytest

from spliceai_batched.broad import (
    compare_fields,
    local_annotations,
    mane_select_score,
    response_parameters_match,
)
from spliceai_batched.broad import (
    main as broad_main,
)


def test_local_annotations_and_broad_comparison(tmp_path: Path) -> None:
    vcf = tmp_path / "scores.vcf"
    vcf.write_text(
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "1\t100\t.\tA\tC\t.\t.\t"
        "SpliceAI=C|GENE|0.10|0.20|0.30|0.40|1|-2|3|-4\n",
        encoding="utf-8",
    )
    local = local_annotations(str(vcf))
    response = {
        "scores": [
            {
                "g_name": "GENE",
                "t_id": "ENST1",
                "t_priority": "MS",
                "DS_AG": "0.10",
                "DS_AL": "0.20",
                "DS_DG": "0.30",
                "DS_DL": "0.40",
                "DP_AG": 1,
                "DP_AL": -2,
                "DP_DG": 3,
                "DP_DL": -4,
            }
        ]
    }
    broad = mane_select_score(json.loads(json.dumps(response)), "GENE")

    assert broad is not None
    result = compare_fields(local["chr1-100-A-C"]["GENE"], broad)
    assert result["max_score_difference"] == 0
    assert result["position_fields_different"] == 0
    assert response_parameters_match(
        {
            "variant": "chr1-100-A-C",
            "hg": "38",
            "distance": 500,
            "mask": 1,
        },
        "chr1-100-A-C",
        500,
        1,
    )


def test_requires_exactly_one_mane_select_match() -> None:
    response = {
        "scores": [
            {"g_name": "GENE", "t_priority": "N"},
            {"g_name": "OTHER", "t_priority": "MS"},
        ]
    }
    assert mane_select_score(response, "GENE") is None


def test_unscored_mnv_is_reported_without_numeric_conversion() -> None:
    result = compare_fields(
        ["AT", "GENE", ".", ".", ".", ".", ".", ".", ".", "."],
        {
            "DS_AG": 0.1,
            "DS_AL": 0.2,
            "DS_DG": 0.3,
            "DS_DL": 0.4,
            "DP_AG": 1,
            "DP_AL": 2,
            "DP_DG": 3,
            "DP_DL": 4,
        },
    )

    assert result["comparison_status"] == "local_unscored"
    assert result["max_score_difference"] == 0.0


def test_unscored_mnv_fails_the_broad_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    variant = "chr1-100-AT-GC"
    vcf = tmp_path / "scores.vcf"
    vcf.write_text(
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "1\t100\t.\tAT\tGC\t.\t.\t"
        "SpliceAI=GC|GENE|.|.|.|.|.|.|.|.\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "queries.tsv"
    manifest.write_text(
        f"variant\tgene\n{variant}\tGENE\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "broad"
    responses_dir = output_dir / "responses"
    responses_dir.mkdir(parents=True)
    response = {
        "variant": variant,
        "hg": 38,
        "distance": 500,
        "mask": 1,
        "scores": [
            {
                "g_name": "GENE",
                "t_id": "ENST1",
                "t_priority": "MS",
                "DS_AG": 0.99,
                "DS_AL": 0.99,
                "DS_DG": 0.99,
                "DS_DL": 0.99,
                "DP_AG": 1,
                "DP_AL": 1,
                "DP_DG": 1,
                "DP_DL": 1,
            }
        ],
    }
    (responses_dir / f"01.{variant}.json").write_text(
        json.dumps(response),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "spliceai-batched-broad",
            "--vcf",
            str(vcf),
            "--manifest",
            str(manifest),
            "--output-dir",
            str(output_dir),
        ],
    )

    with pytest.raises(SystemExit) as raised:
        broad_main()

    assert raised.value.code == 1
    result = json.loads((output_dir / "comparison.json").read_text(encoding="utf-8"))
    assert result["summary"]["comparisons_performed"] == 0
    assert result["summary"]["local_unscored"] == 1
    assert result["summary"]["passed"] is False
    assert "not_all_queries_compared" in result["summary"]["failure_reasons"]
