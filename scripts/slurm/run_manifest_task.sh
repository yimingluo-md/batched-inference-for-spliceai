#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Resolve one manifest row inside a Slurm array task, then run the shard.

set -euo pipefail

: "${MANIFEST:?Set MANIFEST}"
: "${SLURM_ARRAY_TASK_ID:?Set SLURM_ARRAY_TASK_ID}"
: "${RUNNER:?Set RUNNER}"

line="$(
    awk -v task="${SLURM_ARRAY_TASK_ID}" '
        NF && $1 !~ /^#/ {
            seen++
            if (seen == task) {
                print
                exit
            }
        }
    ' "${MANIFEST}"
)"
if [[ -z "${line}" ]]; then
    printf 'No manifest task found for SLURM_ARRAY_TASK_ID=%s\n' \
        "${SLURM_ARRAY_TASK_ID}" >&2
    exit 1
fi

IFS=$'\t' read -r SHARD_ID INPUT_VCF INPUT_SHA256 _ <<< "${line}"
export SHARD_ID INPUT_VCF INPUT_SHA256
if [[ -z "${SHARD_ID}" || -z "${INPUT_VCF}" ]]; then
    printf 'Manifest task %s must contain shard_id and input_vcf\n' \
        "${SLURM_ARRAY_TASK_ID}" >&2
    exit 1
fi

exec "${RUNNER}"
