# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBMIT = ROOT / "scripts" / "slurm" / "submit_array.sh"
RUN_SHARD = ROOT / "scripts" / "slurm" / "run_shard.sh"


def write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


def shard_fingerprint(
    input_vcf: Path,
    reference: Path,
    runner: Path,
    container: Path,
    *,
    container_bind_paths_config: str = "auto",
    container_extra_bind_paths_config: str = "",
    runner_tree_sha256: str | None = None,
) -> str:
    runner_sha256 = hashlib.sha256(runner.read_bytes()).hexdigest()
    fingerprint_content = "\n".join(
        (
            "format_version=3",
            "shard_id=shard-001",
            f"input_sha256={hashlib.sha256(input_vcf.read_bytes()).hexdigest()}",
            f"reference_sha256={hashlib.sha256(reference.read_bytes()).hexdigest()}",
            "annotation_sha256=builtin:grch38",
            f"runner_sha256={runner_sha256}",
            f"runner_tree_sha256={runner_tree_sha256 or runner_sha256}",
            f"container_sha256={hashlib.sha256(container.read_bytes()).hexdigest()}",
            "container_runtime=apptainer",
            f"runner_pythonpath={runner.resolve().parent.parent}",
            f"container_bind_paths_config={container_bind_paths_config}",
            (f"container_extra_bind_paths_config={container_extra_bind_paths_config}"),
            "distance=500",
            "mask=1",
            "batch_size=256",
            "chunk_records=4096",
            "",
        )
    )
    return hashlib.sha256(fingerprint_content.encode()).hexdigest()


def submit_environment(tmp_path: Path) -> tuple[dict[str, str], Path]:
    manifest = tmp_path / "manifest.tsv"
    manifest.write_text("# shard_id\tinput_vcf\nshard-001\t/input/a.vcf.gz\n")
    output_dir = tmp_path / "output"
    result = tmp_path / "result.tsv"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    reference = tmp_path / "reference.fa"
    container = tmp_path / "spliceai.sif"
    cli = tmp_path / "cli.py"
    package_init = tmp_path / "__init__.py"
    reference.write_bytes(b"reference")
    container.write_bytes(b"container")
    cli.write_bytes(b"cli")
    package_init.write_text('__version__ = "0.1.test"\n')

    write_executable(
        fake_bin / "sbatch",
        """#!/bin/sh
exports=
script=
for argument do
    case "${argument}" in
        --export=*) exports="${argument#--export=}" ;;
        --*) ;;
        *) script="${argument}" ;;
    esac
done
test -n "${script}"
old_ifs="${IFS}"
IFS=,
for item in ${exports}; do
    if [ "${item}" != "ALL" ]; then
        export "${item}"
    fi
done
IFS="${old_ifs}"
SLURM_ARRAY_TASK_ID="${TEST_TASK_ID:-1}" "${script}"
""",
    )
    runner = tmp_path / "runner.sh"
    provenance = tmp_path / "provenance.tsv"
    tree_digest = tmp_path / "tree-digest.txt"
    write_executable(
        runner,
        """#!/bin/sh
printf '%s\\t%s\\n' "${SHARD_ID}" "${INPUT_VCF}" > "${RESULT}"
printf '%s\\t%s\\t%s\\n' \
    "${RUNNER_VERSION}" "${GIT_COMMIT}" "${ANNOTATION_SOURCE_URL}" \
    > "${PROVENANCE}"
printf '%s\\n' "${RUNNER_TREE_SHA256}" > "${TREE_DIGEST_RESULT}"
""",
    )

    environment = os.environ.copy()
    environment.update(
        {
            "MANIFEST": str(manifest),
            "OUTPUT_DIR": str(output_dir),
            "REFERENCE": str(reference),
            "ANNOTATION": "grch38",
            "ANNOTATION_RELEASE": "1.5",
            "ANNOTATION_SOURCE_URL": "https://example.test/mane.gtf.gz",
            "ANNOTATION_SOURCE_SHA256": "annotation-source-sha256",
            "SPLICEAI_SIF": str(container),
            "SPLICEAI_BATCHED_SCRIPT": str(cli),
            "RUNNER": str(runner),
            "RESULT": str(result),
            "PROVENANCE": str(provenance),
            "TREE_DIGEST_RESULT": str(tree_digest),
            "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
        }
    )
    return environment, result


def test_submit_array_selects_manifest_row_under_posix_sh(tmp_path) -> None:
    environment, result = submit_environment(tmp_path)

    completed = subprocess.run(
        ["bash", str(SUBMIT)],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert result.read_text() == "shard-001\t/input/a.vcf.gz\n"
    assert Path(environment["PROVENANCE"]).read_text() == (
        "0.1.test\tunknown\thttps://example.test/mane.gtf.gz\n"
    )


def test_submit_array_rejects_missing_task_under_posix_sh(tmp_path) -> None:
    environment, result = submit_environment(tmp_path)
    environment["TEST_TASK_ID"] = "2"

    completed = subprocess.run(
        ["bash", str(SUBMIT)],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "No manifest task found" in completed.stderr
    assert not result.exists()


def test_submit_array_rejects_invalid_staged_range(tmp_path) -> None:
    environment, result = submit_environment(tmp_path)
    environment["ARRAY_START"] = "2"
    environment["ARRAY_END"] = "3"

    completed = subprocess.run(
        ["bash", str(SUBMIT)],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "Invalid array range" in completed.stderr
    assert not result.exists()


def test_submit_array_rejects_missing_runner_from_slurm_spool_copy(
    tmp_path: Path,
) -> None:
    environment, result = submit_environment(tmp_path)
    environment.pop("RUNNER")
    spool_submit = tmp_path / "slurm-spool" / "submit_array.sh"
    spool_submit.parent.mkdir()
    spool_submit.write_bytes(SUBMIT.read_bytes())
    spool_submit.chmod(0o755)

    completed = subprocess.run(
        ["bash", str(spool_submit)],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "RUNNER is not executable" in completed.stderr
    assert "Set RUNNER to an absolute" in completed.stderr
    assert not result.exists()


def test_submit_array_runner_tree_hash_includes_nested_modules(
    tmp_path: Path,
) -> None:
    environment, _ = submit_environment(tmp_path)
    package_root = Path(environment["SPLICEAI_BATCHED_SCRIPT"]).parent
    nested = package_root / "nested"
    nested.mkdir()
    module = nested / "module.py"
    module.write_text("VALUE = 1\n")

    first = subprocess.run(
        ["bash", str(SUBMIT)],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert first.returncode == 0, first.stderr
    digest_path = Path(environment["TREE_DIGEST_RESULT"])
    first_digest = digest_path.read_text().strip()

    module.write_text("VALUE = 2\n")
    second = subprocess.run(
        ["bash", str(SUBMIT)],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert second.returncode == 0, second.stderr
    assert digest_path.read_text().strip() != first_digest


def test_run_shard_skips_verified_completion(tmp_path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    output_vcf = output_dir / "shard-001.vcf.gz"
    output_vcf.write_bytes(b"completed output")
    (output_dir / "shard-001.vcf.gz.tbi").write_bytes(b"index")
    checksum = hashlib.sha256(output_vcf.read_bytes()).hexdigest()
    input_vcf = tmp_path / "input.vcf.gz"
    reference = tmp_path / "reference.fa"
    runner = tmp_path / "cli.py"
    container = tmp_path / "spliceai.sif"
    input_vcf.write_bytes(b"input")
    reference.write_bytes(b"reference")
    runner.write_bytes(b"runner")
    container.write_bytes(b"container")
    fingerprint = shard_fingerprint(
        input_vcf,
        reference,
        runner,
        container,
    )
    (output_dir / "shard-001.complete").write_text(
        f"shard-001\tprevious-job\t17\t{checksum}\t{fingerprint}\n"
    )

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    write_executable(
        fake_bin / "bcftools",
        "#!/bin/sh\nprintf '17\\n'\n",
    )

    environment = os.environ.copy()
    environment.update(
        {
            "INPUT_VCF": str(input_vcf),
            "OUTPUT_DIR": str(output_dir),
            "SHARD_ID": "shard-001",
            "REFERENCE": str(reference),
            "ANNOTATION": "grch38",
            "SPLICEAI_SIF": str(container),
            "SPLICEAI_BATCHED_SCRIPT": str(runner),
            "SLURM_JOB_ID": "current-job",
            "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
        }
    )

    completed = subprocess.run(
        ["bash", str(RUN_SHARD)],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "already complete; skipping" in completed.stdout

    write_executable(fake_bin / "tabix", "#!/bin/sh\nexit 23\n")
    environment["CONTAINER_EXTRA_BIND_PATHS"] = str(tmp_path / "new-runtime")
    environment["WORK_DIR"] = str(tmp_path / "work")
    changed_bind = subprocess.run(
        ["bash", str(RUN_SHARD)],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert changed_bind.returncode != 0
    assert "Completion fingerprint" in changed_bind.stderr
    assert "already complete; skipping" not in changed_bind.stdout


def test_run_shard_rejects_changed_container_at_same_path(tmp_path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    output_vcf = output_dir / "shard-001.vcf.gz"
    output_vcf.write_bytes(b"completed output")
    (output_dir / "shard-001.vcf.gz.tbi").write_bytes(b"index")
    input_vcf = tmp_path / "input.vcf.gz"
    reference = tmp_path / "reference.fa"
    runner = tmp_path / "cli.py"
    container = tmp_path / "spliceai.sif"
    input_vcf.write_bytes(b"input")
    reference.write_bytes(b"reference")
    runner.write_bytes(b"runner")
    container.write_bytes(b"original container")
    output_sha = hashlib.sha256(output_vcf.read_bytes()).hexdigest()
    stale_fingerprint = shard_fingerprint(
        input_vcf,
        reference,
        runner,
        container,
    )
    (output_dir / "shard-001.complete").write_text(
        f"shard-001\tprevious-job\t17\t{output_sha}\t{stale_fingerprint}\n"
    )
    container.write_bytes(b"replacement container")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    write_executable(fake_bin / "bcftools", "#!/bin/sh\nprintf '17\\n'\n")
    environment = os.environ.copy()
    environment.update(
        {
            "INPUT_VCF": str(input_vcf),
            "OUTPUT_DIR": str(output_dir),
            "SHARD_ID": "shard-001",
            "REFERENCE": str(reference),
            "ANNOTATION": "grch38",
            "SPLICEAI_SIF": str(container),
            "SPLICEAI_BATCHED_SCRIPT": str(runner),
            "SLURM_JOB_ID": "current-job",
            "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
        }
    )

    completed = subprocess.run(
        ["bash", str(RUN_SHARD)],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "Completion fingerprint" in completed.stderr
    assert "already complete; skipping" not in completed.stdout
