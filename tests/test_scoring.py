# SPDX-License-Identifier: GPL-3.0-or-later

import numpy as np

from spliceai_batched.scoring import format_score, orient_prediction


def task(**updates):
    base = {
        "alt": "C",
        "gene": "GENE",
        "dist_exon": 99,
        "ref_len": 1,
        "alt_len": 1,
    }
    base.update(updates)
    return base


def test_snv_score_formatting() -> None:
    reference = np.zeros((5, 3), dtype=np.float32)
    alternate = np.zeros((5, 3), dtype=np.float32)
    alternate[3, 1] = 0.5
    alternate[1, 2] = 0.25

    result = format_score(task(), reference, alternate, cov=5, mask=0)
    assert result == "C|GENE|0.50|0.00|0.25|0.00|1|-2|-1|-2"


def test_masked_annotated_gain_is_zero() -> None:
    reference = np.zeros((5, 3), dtype=np.float32)
    alternate = np.zeros((5, 3), dtype=np.float32)
    alternate[3, 1] = 0.5

    result = format_score(
        task(dist_exon=1),
        reference,
        alternate,
        cov=5,
        mask=1,
    )
    assert result.split("|")[2] == "0.00"


def test_simple_deletion_alignment() -> None:
    reference = np.zeros((5, 3), dtype=np.float32)
    alternate = np.zeros((4, 3), dtype=np.float32)
    result = format_score(
        task(ref_len=2, alt_len=1),
        reference,
        alternate,
        cov=5,
        mask=0,
    )
    assert len(result.split("|")) == 10


def test_deletion_uses_upstream_float64_alignment() -> None:
    reference = np.zeros((5, 3), dtype=np.float32)
    alternate = np.zeros((4, 3), dtype=np.float32)
    reference[0, 1] = np.float32(0.11566238)
    alternate[0, 1] = np.float32(0.5006624)

    result = format_score(
        task(ref_len=2, alt_len=1),
        reference,
        alternate,
        cov=5,
        mask=0,
    )
    assert result.split("|")[2] == "0.39"


def test_minus_strand_prediction_is_returned_to_genomic_order() -> None:
    prediction = np.arange(15).reshape(5, 3)
    assert np.array_equal(
        orient_prediction(prediction, reverse=True),
        prediction[::-1],
    )
    assert orient_prediction(prediction, reverse=False) is prediction
