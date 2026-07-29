#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Generate one reference-derived variant-universe shard.

set -euo pipefail

: "${UNIVERSE_PLAN:?Set UNIVERSE_PLAN}"
: "${UNIVERSE_DIR:?Set UNIVERSE_DIR}"
: "${REFERENCE:?Set REFERENCE}"
: "${REFERENCE_SHA256:?Set REFERENCE_SHA256}"
: "${SLURM_ARRAY_TASK_ID:?Run this script as a Slurm array}"

spliceai-batched-universe generate \
    --plan "${UNIVERSE_PLAN}" \
    --task-id "${SLURM_ARRAY_TASK_ID}" \
    --output-dir "${UNIVERSE_DIR}" \
    --reference "${REFERENCE}" \
    --reference-sha256 "${REFERENCE_SHA256}" \
    --threads "${SLURM_CPUS_PER_TASK:-1}"
