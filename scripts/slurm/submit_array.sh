#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Submit a manifest-driven Slurm GPU array.

set -euo pipefail

: "${MANIFEST:?Set MANIFEST to a TSV: shard_id, input_vcf[, input_sha256]}"
: "${OUTPUT_DIR:?Set OUTPUT_DIR}"
: "${REFERENCE:?Set REFERENCE}"
: "${ANNOTATION:?Set ANNOTATION}"
: "${SPLICEAI_SIF:?Set SPLICEAI_SIF}"
: "${SPLICEAI_BATCHED_SCRIPT:?Set SPLICEAI_BATCHED_SCRIPT}"

RUNNER="${RUNNER:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/run_shard.sh}"
if [[ ! -x "${RUNNER}" ]]; then
    printf 'RUNNER is not executable: %s\n' "${RUNNER}" >&2
    printf 'Set RUNNER to an absolute run_shard.sh path when invoking this submitter from another Slurm job.\n' >&2
    exit 1
fi
RUNNER="$(readlink -f -- "${RUNNER}")"
TASK_RUNNER="$(
    cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &&
        pwd -P
)/run_manifest_task.sh"
TASK_RUNNER="${SLURM_TASK_RUNNER:-${TASK_RUNNER}}"
if [[ ! -x "${TASK_RUNNER}" ]]; then
    printf 'Slurm task runner is not executable: %s\n' "${TASK_RUNNER}" >&2
    exit 1
fi
TASK_RUNNER="$(readlink -f -- "${TASK_RUNNER}")"
REFERENCE="$(readlink -f -- "${REFERENCE}")"
if [[ -f "${ANNOTATION}" ]]; then
    ANNOTATION="$(readlink -f -- "${ANNOTATION}")"
fi
SPLICEAI_SIF="$(readlink -f -- "${SPLICEAI_SIF}")"
SPLICEAI_BATCHED_SCRIPT="$(readlink -f -- "${SPLICEAI_BATCHED_SCRIPT}")"
SCRIPT_DIR="$(cd -- "$(dirname -- "${SPLICEAI_BATCHED_SCRIPT}")" && pwd -P)"
SPLICEAI_BATCHED_PYTHONPATH="$(
    cd -- "$(dirname -- "${SCRIPT_DIR}")" &&
        pwd -P
)"

if [[ -z "${RUNNER_VERSION:-}" ]] && [[ -f "${SCRIPT_DIR}/__init__.py" ]]; then
    RUNNER_VERSION="$(
        awk -F'"' '/^__version__[[:space:]]*=/ {print $2; exit}' \
            "${SCRIPT_DIR}/__init__.py"
    )"
fi
RUNNER_VERSION="${RUNNER_VERSION:-unknown}"

if [[ -z "${GIT_COMMIT:-}" ]] && command -v git >/dev/null 2>&1; then
    GIT_COMMIT="$(
        git -C "${SCRIPT_DIR}" rev-parse HEAD 2>/dev/null || true
    )"
fi
GIT_COMMIT="${GIT_COMMIT:-unknown}"

# Hash shared assets once here instead of once per array task. Callers may
# provide precomputed values when submission runs on a host without the assets.
REFERENCE_SHA256="${REFERENCE_SHA256:-$(sha256sum "${REFERENCE}" | cut -d' ' -f1)}"
if [[ -f "${ANNOTATION}" ]]; then
    ANNOTATION_SHA256="${ANNOTATION_SHA256:-$(sha256sum "${ANNOTATION}" | cut -d' ' -f1)}"
else
    ANNOTATION_SHA256="${ANNOTATION_SHA256:-builtin:${ANNOTATION}}"
fi
RUNNER_SHA256="${RUNNER_SHA256:-$(sha256sum "${SPLICEAI_BATCHED_SCRIPT}" | cut -d' ' -f1)}"
RUNNER_TREE_SHA256="${RUNNER_TREE_SHA256:-$(
    (
        cd -- "${SCRIPT_DIR}"
        find . -type f -name '*.py' -print0 |
            LC_ALL=C sort -z |
            xargs -0 sha256sum
    ) | sha256sum | cut -d' ' -f1
)}"
CONTAINER_SHA256="${CONTAINER_SHA256:-$(sha256sum "${SPLICEAI_SIF}" | cut -d' ' -f1)}"

TASKS="$(awk 'NF && $1 !~ /^#/ {count++} END {print count+0}' "${MANIFEST}")"
if [[ "${TASKS}" -lt 1 ]]; then
    echo "Manifest contains no tasks" >&2
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

mkdir -p "${OUTPUT_DIR}/logs"

SBATCH_ARGS=(
    --job-name=spliceai-batched \
    --gres="${SBATCH_GRES:-gpu:1}" \
    --cpus-per-task="${SBATCH_CPUS_PER_TASK:-4}" \
    --mem="${SBATCH_MEMORY:-64g}" \
    --time="${WALLTIME:-08:00:00}" \
    --array="${ARRAY_START}-${ARRAY_END}%${MAX_CONCURRENT:-32}" \
    --output="${OUTPUT_DIR}/logs/%A_%a.out" \
    --error="${OUTPUT_DIR}/logs/%A_%a.err" \
    --export="ALL,MANIFEST=${MANIFEST},OUTPUT_DIR=${OUTPUT_DIR},REFERENCE=${REFERENCE},REFERENCE_SHA256=${REFERENCE_SHA256},ANNOTATION=${ANNOTATION},ANNOTATION_SHA256=${ANNOTATION_SHA256},ANNOTATION_RELEASE=${ANNOTATION_RELEASE:-unknown},ANNOTATION_SOURCE_URL=${ANNOTATION_SOURCE_URL:-unknown},ANNOTATION_SOURCE_SHA256=${ANNOTATION_SOURCE_SHA256:-unknown},SPLICEAI_SIF=${SPLICEAI_SIF},CONTAINER_SHA256=${CONTAINER_SHA256},SPLICEAI_BATCHED_SCRIPT=${SPLICEAI_BATCHED_SCRIPT},SPLICEAI_BATCHED_PYTHONPATH=${SPLICEAI_BATCHED_PYTHONPATH},RUNNER_SHA256=${RUNNER_SHA256},RUNNER_TREE_SHA256=${RUNNER_TREE_SHA256},RUNNER_VERSION=${RUNNER_VERSION},GIT_COMMIT=${GIT_COMMIT},RUNNER=${RUNNER},CONTAINER_RUNTIME=${CONTAINER_RUNTIME:-apptainer},CONTAINER_EXTRA_BIND_PATHS=${CONTAINER_EXTRA_BIND_PATHS:-}"
)
if [[ -n "${SBATCH_PARTITION:-}" ]]; then
    SBATCH_ARGS+=(--partition="${SBATCH_PARTITION}")
fi
if [[ -n "${SBATCH_CONSTRAINT:-}" ]]; then
    SBATCH_ARGS+=(--constraint="${SBATCH_CONSTRAINT}")
fi

sbatch "${SBATCH_ARGS[@]}" "${TASK_RUNNER}"
