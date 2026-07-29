# SPDX-License-Identifier: GPL-3.0-or-later
# Adapted from SpliceAI 1.3.1, Copyright (c) 2013-2018 Illumina, Inc.
# Substantially modified in 2026 by Yiming Luo; see NOTICE.
"""Numerical post-processing functions isolated for unit testing."""

from __future__ import annotations

from typing import Any

import numpy as np


def orient_prediction(prediction: np.ndarray, reverse: bool) -> np.ndarray:
    """Return predictions in forward genomic coordinate order."""
    return prediction[::-1] if reverse else prediction


def format_score(
    task: dict[str, Any],
    y_ref: np.ndarray,
    y_alt: np.ndarray,
    cov: int,
    mask: int,
) -> str:
    """Apply indel alignment, masking, and two-decimal VCF formatting."""
    ref_len = task["ref_len"]
    alt_len = task["alt_len"]
    del_len = max(ref_len - alt_len, 0)

    if ref_len > 1 and alt_len == 1:
        y_alt = np.concatenate(
            (
                y_alt[: cov // 2 + alt_len],
                np.zeros((del_len, 3)),
                y_alt[cov // 2 + alt_len :],
            ),
            axis=0,
        )
    elif ref_len == 1 and alt_len > 1:
        y_alt = np.concatenate(
            (
                y_alt[: cov // 2],
                np.max(y_alt[cov // 2 : cov // 2 + alt_len], axis=0)[None, :],
                y_alt[cov // 2 + alt_len :],
            ),
            axis=0,
        )

    gain_acceptor = y_alt[:, 1] - y_ref[:, 1]
    loss_acceptor = y_ref[:, 1] - y_alt[:, 1]
    gain_donor = y_alt[:, 2] - y_ref[:, 2]
    loss_donor = y_ref[:, 2] - y_alt[:, 2]

    idx_pa = int(gain_acceptor.argmax())
    idx_na = int(loss_acceptor.argmax())
    idx_pd = int(gain_donor.argmax())
    idx_nd = int(loss_donor.argmax())
    dist_exon = task["dist_exon"]

    mask_pa = bool(mask and idx_pa - cov // 2 == dist_exon)
    mask_na = bool(mask and idx_na - cov // 2 != dist_exon)
    mask_pd = bool(mask and idx_pd - cov // 2 == dist_exon)
    mask_nd = bool(mask and idx_nd - cov // 2 != dist_exon)

    return "{}|{}|{:.2f}|{:.2f}|{:.2f}|{:.2f}|{}|{}|{}|{}".format(
        task["alt"],
        task["gene"],
        gain_acceptor[idx_pa] * (1 - mask_pa),
        loss_acceptor[idx_na] * (1 - mask_na),
        gain_donor[idx_pd] * (1 - mask_pd),
        loss_donor[idx_nd] * (1 - mask_nd),
        idx_pa - cov // 2,
        idx_na - cov // 2,
        idx_pd - cov // 2,
        idx_nd - cov // 2,
    )
