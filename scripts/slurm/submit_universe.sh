#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Submit CPU jobs that generate clean variant-universe VCF shards.

set -euo pipefail

: "${UNIVERSE_PLAN:?Set UNIVERSE_PLAN}"
: "${UNIVERSE_DIR:?Set UNIVERSE_DIR}"
: "${REFERENCE:?Set REFERENCE}"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TASK_RUNNER="${UNIVERSE_TASK_RUNNER:-${SCRIPT_DIR}/generate_universe_task.sh}"
PLAN_REFERENCE_SHA256="$(
    awk -F= '$1 == "##reference_sha256" {print $2; exit}' "${UNIVERSE_PLAN}"
)"
if [[ -z "${PLAN_REFERENCE_SHA256}" ]]; then
    echo "Universe plan has no reference_sha256" >&2
    exit 1
fi
REFERENCE_SHA256="${REFERENCE_SHA256:-$(sha256sum "${REFERENCE}" | cut -d' ' -f1)}"
if [[ "${REFERENCE_SHA256}" != "${PLAN_REFERENCE_SHA256}" ]]; then
    echo "Reference checksum does not match the universe plan" >&2
    exit 1
fi
TASKS="$(
    awk 'NF && $1 !~ /^#/ {count++} END {print count+0}' "${UNIVERSE_PLAN}"
)"
if [[ "${TASKS}" -lt 1 ]]; then
    echo "Universe plan contains no tasks" >&2
    exit 1
fi
ARRAY_START="${ARRAY_START:-1}"
ARRAY_END="${ARRAY_END:-${TASKS}}"
if [[ "${ARRAY_START}" -lt 1 ]] \
    || [[ "${ARRAY_END}" -lt "${ARRAY_START}" ]] \
    || [[ "${ARRAY_END}" -gt "${TASKS}" ]]; then
    echo "Invalid array range ${ARRAY_START}-${ARRAY_END} for ${TASKS} tasks" >&2
    exit 1
fi

mkdir -p "${UNIVERSE_DIR}/logs"

SBATCH_ARGS=(
    --job-name=spliceai-universe
    --cpus-per-task="${SBATCH_CPUS_PER_TASK:-2}"
    --mem="${SBATCH_MEMORY:-8g}"
    --time="${WALLTIME:-04:00:00}"
    --array="${ARRAY_START}-${ARRAY_END}%${MAX_CONCURRENT:-16}"
    --output="${UNIVERSE_DIR}/logs/%A_%a.out"
    --error="${UNIVERSE_DIR}/logs/%A_%a.err"
    --export="ALL,UNIVERSE_PLAN=${UNIVERSE_PLAN},UNIVERSE_DIR=${UNIVERSE_DIR},REFERENCE=${REFERENCE},REFERENCE_SHA256=${REFERENCE_SHA256}"
)
if [[ -n "${SBATCH_PARTITION:-}" ]]; then
    SBATCH_ARGS+=(--partition="${SBATCH_PARTITION}")
fi

sbatch "${SBATCH_ARGS[@]}" "${TASK_RUNNER}"
