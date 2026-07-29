#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

: "${OFFICIAL_VCF:?Set OFFICIAL_VCF}"
: "${OPTIMIZED_VCF:?Set OPTIMIZED_VCF}"
: "${REPORT_JSON:?Set REPORT_JSON}"

spliceai-batched-compare \
    "${OFFICIAL_VCF}" \
    "${OPTIMIZED_VCF}" \
    --max-score-difference 0.011 \
    --json "${REPORT_JSON}"
