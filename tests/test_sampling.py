# SPDX-License-Identifier: GPL-3.0-or-later

from spliceai_batched.sampling import evenly_spaced_indexes, quantile_rows


def test_single_quantile_selects_middle_row() -> None:
    rows = [{"value": str(index)} for index in range(5)]
    assert quantile_rows(rows, 1) == [{"value": "2"}]


def test_single_target_index_selects_middle() -> None:
    assert evenly_spaced_indexes(6, 1) == [2]


def test_nonpositive_sample_count_is_rejected() -> None:
    try:
        evenly_spaced_indexes(6, 0)
    except ValueError as error:
        assert str(error) == "count must be at least 1"
    else:
        raise AssertionError("expected ValueError")
