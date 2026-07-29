#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Run one restartable batched-inference shard on a Slurm GPU node.

set -euo pipefail

: "${INPUT_VCF:?Set INPUT_VCF to an indexed BGZF VCF shard}"
: "${OUTPUT_DIR:?Set OUTPUT_DIR}"
: "${SHARD_ID:?Set SHARD_ID}"
: "${REFERENCE:?Set REFERENCE to an indexed FASTA}"
: "${ANNOTATION:?Set ANNOTATION to grch38 or a custom annotation path}"
: "${SPLICEAI_SIF:?Set SPLICEAI_SIF to a separately obtained container}"
: "${SPLICEAI_BATCHED_SCRIPT:?Set SPLICEAI_BATCHED_SCRIPT to cli.py}"

BATCH_SIZE="${BATCH_SIZE:-256}"
CHUNK_RECORDS="${CHUNK_RECORDS:-4096}"
DISTANCE="${DISTANCE:-500}"
MASK="${MASK:-1}"
CONTAINER_RUNTIME="${CONTAINER_RUNTIME:-apptainer}"
RUNNER_VERSION="${RUNNER_VERSION:-unknown}"
GIT_COMMIT="${GIT_COMMIT:-unknown}"
ANNOTATION_RELEASE="${ANNOTATION_RELEASE:-unknown}"
ANNOTATION_SOURCE_URL="${ANNOTATION_SOURCE_URL:-unknown}"
ANNOTATION_SOURCE_SHA256="${ANNOTATION_SOURCE_SHA256:-unknown}"
WORK_ROOT="${SLURM_TMPDIR:-${TMPDIR:-/tmp}}"
WORK_DIR="${WORK_DIR:-${WORK_ROOT}/spliceai-batched-${SLURM_JOB_ID}}"

mkdir -p "${OUTPUT_DIR}"

completion="${OUTPUT_DIR}/${SHARD_ID}.complete"
completed_vcf="${OUTPUT_DIR}/${SHARD_ID}.vcf.gz"
completed_index="${completed_vcf}.tbi"
completion_is_intact=0
if [[ -f "${completion}" ]]; then
    marker_shard=""
    marker_job=""
    marker_records=""
    marker_sha256=""
    marker_fingerprint=""
    read -r marker_shard marker_job marker_records marker_sha256 marker_fingerprint \
        < "${completion}" || true
    if [[ "${marker_shard}" == "${SHARD_ID}" ]] \
        && [[ -n "${marker_records}" ]] \
        && [[ -n "${marker_sha256}" ]] \
        && [[ -s "${completed_vcf}" ]] \
        && [[ -s "${completed_index}" ]] \
        && [[ "$(sha256sum "${completed_vcf}" | cut -d' ' -f1)" == "${marker_sha256}" ]] \
        && [[ "$(bcftools index --nrecords "${completed_vcf}")" == "${marker_records}" ]]; then
        completion_is_intact=1
    else
        printf 'Completion state for shard %s is incomplete or inconsistent; rerunning.\n' \
            "${SHARD_ID}" >&2
    fi
fi

REFERENCE="$(readlink -f -- "${REFERENCE}")"
if [[ -f "${ANNOTATION}" ]]; then
    ANNOTATION="$(readlink -f -- "${ANNOTATION}")"
fi
SPLICEAI_SIF="$(readlink -f -- "${SPLICEAI_SIF}")"
SPLICEAI_BATCHED_SCRIPT="$(readlink -f -- "${SPLICEAI_BATCHED_SCRIPT}")"
SCRIPT_DIR="$(cd -- "$(dirname -- "${SPLICEAI_BATCHED_SCRIPT}")" && pwd -P)"
SPLICEAI_BATCHED_PYTHONPATH="${SPLICEAI_BATCHED_PYTHONPATH:-$(
    cd -- "$(dirname -- "${SCRIPT_DIR}")" &&
        pwd -P
)}"
SPLICEAI_BATCHED_PYTHONPATH="$(
    cd -- "${SPLICEAI_BATCHED_PYTHONPATH}" &&
        pwd -P
)"
container_bind_paths_config="${CONTAINER_BIND_PATHS:-auto}"
container_extra_bind_paths_config="${CONTAINER_EXTRA_BIND_PATHS:-}"

if [[ -f "${ANNOTATION}" ]]; then
    annotation_sha256="${ANNOTATION_SHA256:-$(sha256sum "${ANNOTATION}" | cut -d' ' -f1)}"
else
    annotation_sha256="${ANNOTATION_SHA256:-builtin:${ANNOTATION}}"
fi
input_sha256="${INPUT_SHA256:-$(sha256sum "${INPUT_VCF}" | cut -d' ' -f1)}"
reference_sha256="${REFERENCE_SHA256:-$(sha256sum "${REFERENCE}" | cut -d' ' -f1)}"
runner_sha256="${RUNNER_SHA256:-$(sha256sum "${SPLICEAI_BATCHED_SCRIPT}" | cut -d' ' -f1)}"
runner_tree_sha256="${RUNNER_TREE_SHA256:-${runner_sha256}}"
container_sha256="${CONTAINER_SHA256:-$(sha256sum "${SPLICEAI_SIF}" | cut -d' ' -f1)}"
run_fingerprint="$(
    {
        printf 'format_version=3\n'
        printf 'shard_id=%s\n' "${SHARD_ID}"
        printf 'input_sha256=%s\n' "${input_sha256}"
        printf 'reference_sha256=%s\n' "${reference_sha256}"
        printf 'annotation_sha256=%s\n' "${annotation_sha256}"
        printf 'runner_sha256=%s\n' "${runner_sha256}"
        printf 'runner_tree_sha256=%s\n' "${runner_tree_sha256}"
        printf 'container_sha256=%s\n' "${container_sha256}"
        printf 'container_runtime=%s\n' "${CONTAINER_RUNTIME}"
        printf 'runner_pythonpath=%s\n' "${SPLICEAI_BATCHED_PYTHONPATH}"
        printf 'container_bind_paths_config=%s\n' \
            "${container_bind_paths_config}"
        printf 'container_extra_bind_paths_config=%s\n' \
            "${container_extra_bind_paths_config}"
        printf 'distance=%s\n' "${DISTANCE}"
        printf 'mask=%s\n' "${MASK}"
        printf 'batch_size=%s\n' "${BATCH_SIZE}"
        printf 'chunk_records=%s\n' "${CHUNK_RECORDS}"
    } | sha256sum | cut -d' ' -f1
)"

if [[ "${completion_is_intact}" -eq 1 ]]; then
    if [[ "${marker_fingerprint}" == "${run_fingerprint}" ]]; then
        printf 'Shard %s is already complete; skipping (job %s, records %s).\n' \
            "${SHARD_ID}" "${marker_job}" "${marker_records}"
        exit 0
    fi
    printf 'Completion fingerprint for shard %s does not match; rerunning.\n' \
        "${SHARD_ID}" >&2
fi

mkdir -p "${WORK_DIR}"

bind_paths=(
    "$(cd -- "${WORK_DIR}" && pwd -P)"
    "${SPLICEAI_BATCHED_PYTHONPATH}"
    "$(cd -- "$(dirname -- "${REFERENCE}")" && pwd -P)"
)
if [[ -f "${ANNOTATION}" ]]; then
    bind_paths+=("$(cd -- "$(dirname -- "${ANNOTATION}")" && pwd -P)")
fi
if [[ -z "${CONTAINER_BIND_PATHS:-}" ]]; then
    CONTAINER_BIND_PATHS="$(
        IFS=,
        printf '%s' "${bind_paths[*]}"
    )"
fi
if [[ -n "${container_extra_bind_paths_config}" ]]; then
    extra_bind_paths="${container_extra_bind_paths_config//:/,}"
    CONTAINER_BIND_PATHS="${CONTAINER_BIND_PATHS},${extra_bind_paths}"
fi

export TF_DETERMINISTIC_OPS=1
export TF_CUDNN_DETERMINISTIC=1
export TF_USE_CUDNN_AUTOTUNE=0
export APPTAINERENV_PYTHONNOUSERSITE=1
export SINGULARITYENV_PYTHONNOUSERSITE=1
export APPTAINERENV_SPLICEAI_BATCHED_GIT_COMMIT="${GIT_COMMIT}"
export SINGULARITYENV_SPLICEAI_BATCHED_GIT_COMMIT="${GIT_COMMIT}"
export APPTAINERENV_PYTHONPATH="${SPLICEAI_BATCHED_PYTHONPATH}"
export SINGULARITYENV_PYTHONPATH="${SPLICEAI_BATCHED_PYTHONPATH}"

cp "${INPUT_VCF}" "${WORK_DIR}/input.vcf.gz"
if [[ -f "${INPUT_VCF}.tbi" ]]; then
    cp "${INPUT_VCF}.tbi" "${WORK_DIR}/input.vcf.gz.tbi"
else
    tabix --preset vcf "${WORK_DIR}/input.vcf.gz"
fi

metadata="${OUTPUT_DIR}/${SHARD_ID}.${SLURM_JOB_ID}.metadata.txt"
time_log="${OUTPUT_DIR}/${SHARD_ID}.${SLURM_JOB_ID}.time.txt"
gpu_details="$(
    nvidia-smi \
        --query-gpu=name,driver_version,memory.total \
        --format=csv,noheader,nounits |
        head -n 1
)"
IFS=',' read -r gpu_model driver_version gpu_memory_total_mib \
    <<< "${gpu_details}"
gpu_model="$(printf '%s' "${gpu_model}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
driver_version="$(printf '%s' "${driver_version}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
gpu_memory_total_mib="$(printf '%s' "${gpu_memory_total_mib}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"

{
    printf 'job_id=%s\n' "${SLURM_JOB_ID}"
    printf 'node=%s\n' "$(hostname)"
    printf 'shard_id=%s\n' "${SHARD_ID}"
    printf 'distance=%s\n' "${DISTANCE}"
    printf 'mask=%s\n' "${MASK}"
    printf 'batch_size=%s\n' "${BATCH_SIZE}"
    printf 'chunk_records=%s\n' "${CHUNK_RECORDS}"
    printf 'runner_version=%s\n' "${RUNNER_VERSION}"
    printf 'git_commit=%s\n' "${GIT_COMMIT}"
    printf 'container=%s\n' "${SPLICEAI_SIF}"
    printf 'container_sha256=%s\n' "${container_sha256}"
    printf 'container_digest=sha256:%s\n' "${container_sha256}"
    printf 'container_runtime=%s\n' "${CONTAINER_RUNTIME}"
    printf 'reference=%s\n' "${REFERENCE}"
    printf 'reference_path=%s\n' "${REFERENCE}"
    printf 'reference_sha256=%s\n' "${reference_sha256}"
    printf 'annotation=%s\n' "${ANNOTATION}"
    printf 'annotation_path=%s\n' "${ANNOTATION}"
    printf 'annotation_release=%s\n' "${ANNOTATION_RELEASE}"
    printf 'annotation_source_url=%s\n' "${ANNOTATION_SOURCE_URL}"
    printf 'annotation_source_sha256=%s\n' "${ANNOTATION_SOURCE_SHA256}"
    printf 'annotation_sha256=%s\n' "${annotation_sha256}"
    printf 'runner_sha256=%s\n' "${runner_sha256}"
    printf 'runner_tree_sha256=%s\n' "${runner_tree_sha256}"
    printf 'runner_pythonpath=%s\n' "${SPLICEAI_BATCHED_PYTHONPATH}"
    printf 'container_bind_paths=%s\n' "${CONTAINER_BIND_PATHS}"
    printf 'container_extra_bind_paths=%s\n' \
        "${CONTAINER_EXTRA_BIND_PATHS:-}"
    printf 'input_sha256=%s\n' "${input_sha256}"
    printf 'run_fingerprint=%s\n' "${run_fingerprint}"
    printf 'started_at=%s\n' "$(date --iso-8601=seconds)"
    printf 'gpu_model=%s\n' "${gpu_model}"
    printf 'driver_version=%s\n' "${driver_version}"
    printf 'gpu_memory_total_mib=%s\n' "${gpu_memory_total_mib}"
} > "${metadata}"

/usr/bin/time -v \
    "${CONTAINER_RUNTIME}" exec --nv \
    --bind "${CONTAINER_BIND_PATHS}" \
    "${SPLICEAI_SIF}" \
    python "${SPLICEAI_BATCHED_SCRIPT}" \
    -I "${WORK_DIR}/input.vcf.gz" \
    -O "${WORK_DIR}/${SHARD_ID}.vcf.gz" \
    -R "${REFERENCE}" \
    -A "${ANNOTATION}" \
    -D "${DISTANCE}" \
    -M "${MASK}" \
    --batch-size "${BATCH_SIZE}" \
    --chunk-records "${CHUNK_RECORDS}" \
    2> "${time_log}"

tabix --preset vcf "${WORK_DIR}/${SHARD_ID}.vcf.gz"

records_in="$(bcftools index --nrecords "${WORK_DIR}/input.vcf.gz")"
records_out="$(bcftools index --nrecords "${WORK_DIR}/${SHARD_ID}.vcf.gz")"
if [[ "${records_in}" != "${records_out}" ]]; then
    printf 'Record-count mismatch: input=%s output=%s\n' \
        "${records_in}" "${records_out}" >&2
    exit 1
fi

cp "${WORK_DIR}/${SHARD_ID}.vcf.gz" \
    "${WORK_DIR}/${SHARD_ID}.vcf.gz.tbi" \
    "${OUTPUT_DIR}/"

output_sha256="$(
    sha256sum "${OUTPUT_DIR}/${SHARD_ID}.vcf.gz" | cut -d' ' -f1
)"
{
    printf 'input_records=%s\n' "${records_in}"
    printf 'output_records=%s\n' "${records_out}"
    printf 'output_sha256=%s\n' "${output_sha256}"
    printf 'finished_at=%s\n' "$(date --iso-8601=seconds)"
} >> "${metadata}"

completion_tmp="${OUTPUT_DIR}/.${SHARD_ID}.complete.${SLURM_JOB_ID}"
printf '%s\t%s\t%s\t%s\t%s\n' \
    "${SHARD_ID}" "${SLURM_JOB_ID}" "${records_out}" "${output_sha256}" \
    "${run_fingerprint}" \
    > "${completion_tmp}"
mv "${completion_tmp}" "${completion}"
