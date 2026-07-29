# SPDX-License-Identifier: GPL-3.0-or-later
"""Plan and generate a reference-derived MANE variant universe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterator, TextIO

import pysam

DNA_BASES = ("A", "C", "G", "T")
RECORDS_PER_BASE = {"snv": 3, "indel": 8}
PLAN_COLUMNS = ("shard_id", "kind", "regions", "estimated_records")
UNIVERSE_DEFINITIONS = {
    "snv": "three non-reference SNVs at every A/C/G/T anchor",
    "indel": (
        "four single-base insertions and reference deletions of 1-4 bases "
        "at every A/C/G/T anchor"
    ),
}


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verified_sha256(
    path: str,
    expected: str | None = None,
    label: str = "File",
) -> str:
    actual = sha256_file(path)
    if expected is not None and actual != expected.lower():
        raise ValueError(
            f"{label} checksum mismatch: expected {expected.lower()}, got {actual}"
        )
    return actual


def parse_annotation_intervals(path: str) -> dict[str, list[tuple[int, int]]]:
    intervals: dict[str, list[tuple[int, int]]] = defaultdict(list)
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 7:
                raise ValueError(f"{path}:{line_number}: expected 7 annotation columns")
            chrom = fields[1]
            try:
                start = int(fields[3])
                end = int(fields[4])
            except ValueError as exc:
                raise ValueError(
                    f"{path}:{line_number}: invalid transcript coordinates"
                ) from exc
            if start < 0 or end <= start:
                raise ValueError(
                    f"{path}:{line_number}: invalid half-open interval "
                    f"{chrom}:{start}-{end}"
                )
            intervals[chrom].append((start, end))
    if not intervals:
        raise ValueError(f"No transcript intervals found in {path}")
    return dict(intervals)


def merge_intervals(
    intervals: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def resolve_reference_contig(annotation_contig: str, references: set[str]) -> str:
    candidates = [annotation_contig]
    if annotation_contig.startswith("chr"):
        candidates.append(annotation_contig[3:])
    else:
        candidates.append(f"chr{annotation_contig}")
    if annotation_contig == "MT":
        candidates.extend(["M", "chrM"])
    elif annotation_contig in {"M", "chrM"}:
        candidates.extend(["MT", "chrMT"])
    matches = list(
        dict.fromkeys(candidate for candidate in candidates if candidate in references)
    )
    if len(matches) != 1:
        raise ValueError(
            f"Could not uniquely map annotation contig {annotation_contig!r} "
            "to the reference FASTA"
        )
    return matches[0]


def reference_intervals(
    annotation_path: str,
    reference_path: str,
) -> tuple[
    list[str],
    dict[str, list[tuple[int, int]]],
    dict[str, str],
    dict[str, int],
]:
    annotation_intervals = parse_annotation_intervals(annotation_path)
    with pysam.FastaFile(reference_path) as reference:
        contig_order = list(reference.references)
        lengths = dict(zip(reference.references, reference.lengths))
    reference_names = set(contig_order)
    mapped: dict[str, list[tuple[int, int]]] = {}
    reference_contigs: dict[str, str] = {}
    for annotation_contig, intervals in annotation_intervals.items():
        reference_contig = resolve_reference_contig(
            annotation_contig,
            reference_names,
        )
        for start, end in intervals:
            if end > lengths[reference_contig]:
                raise ValueError(
                    f"Annotation interval {annotation_contig}:{start}-{end} "
                    f"exceeds reference contig length {lengths[reference_contig]}"
                )
        mapped[annotation_contig] = merge_intervals(intervals)
        reference_contigs[annotation_contig] = reference_contig
    annotation_order = sorted(
        mapped,
        key=lambda contig: contig_order.index(reference_contigs[contig]),
    )
    return annotation_order, mapped, reference_contigs, lengths


def packed_regions(
    intervals: list[tuple[int, int]],
    bases_per_shard: int,
) -> Iterator[list[tuple[int, int]]]:
    current: list[tuple[int, int]] = []
    current_bases = 0
    for interval_start, interval_end in intervals:
        start = interval_start
        while start < interval_end:
            capacity = bases_per_shard - current_bases
            end = min(interval_end, start + capacity)
            current.append((start, end))
            current_bases += end - start
            start = end
            if current_bases == bases_per_shard:
                yield current
                current = []
                current_bases = 0
    if current:
        yield current


def write_plan(
    annotation_path: str,
    reference_path: str,
    output_path: str,
    target_records: int = 1_000_000,
    kinds: tuple[str, ...] = ("snv", "indel"),
    annotation_release: str = "unknown",
    annotation_sha256: str | None = None,
    reference_sha256: str | None = None,
) -> dict[str, int]:
    if target_records < max(RECORDS_PER_BASE.values()):
        raise ValueError("--target-records is too small")
    invalid_kinds = set(kinds) - set(RECORDS_PER_BASE)
    if invalid_kinds:
        raise ValueError(f"Unsupported variant kinds: {sorted(invalid_kinds)}")

    (
        contig_order,
        intervals_by_contig,
        reference_contigs,
        _,
    ) = reference_intervals(annotation_path, reference_path)
    annotation_digest = verified_sha256(
        annotation_path,
        annotation_sha256,
        "Annotation",
    )
    reference_digest = verified_sha256(
        reference_path,
        reference_sha256,
        "Reference",
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    task_counts = {kind: 0 for kind in kinds}
    estimated_counts = {kind: 0 for kind in kinds}
    merged_bases = sum(
        end - start
        for intervals in intervals_by_contig.values()
        for start, end in intervals
    )
    with output.open("w", encoding="utf-8") as handle:
        handle.write("##format_version=2\n")
        handle.write(f"##reference={Path(reference_path).resolve()}\n")
        handle.write(f"##reference_sha256={reference_digest}\n")
        handle.write(f"##annotation={Path(annotation_path).resolve()}\n")
        handle.write(f"##annotation_release={annotation_release}\n")
        handle.write(f"##annotation_sha256={annotation_digest}\n")
        handle.write(f"##target_records={target_records}\n")
        handle.write(f"##merged_transcript_bases={merged_bases}\n")
        handle.write("#" + "\t".join(PLAN_COLUMNS) + "\n")
        for kind in kinds:
            bases_per_shard = max(1, target_records // RECORDS_PER_BASE[kind])
            shard_number = 0
            for contig in contig_order:
                intervals = intervals_by_contig.get(contig, [])
                for regions in packed_regions(intervals, bases_per_shard):
                    shard_number += 1
                    reference_contig = reference_contigs[contig]
                    region_values = [
                        [contig, reference_contig, start, end] for start, end in regions
                    ]
                    estimated = (
                        sum(end - start for start, end in regions)
                        * RECORDS_PER_BASE[kind]
                    )
                    handle.write(
                        f"{kind}-{shard_number:06d}\t{kind}\t"
                        f"{json.dumps(region_values, separators=(',', ':'))}\t"
                        f"{estimated}\n"
                    )
                    estimated_counts[kind] += estimated
            task_counts[kind] = shard_number

    result = {"merged_transcript_bases": merged_bases}
    for kind in kinds:
        result[f"{kind}_tasks"] = task_counts[kind]
        result[f"{kind}_estimated_records"] = estimated_counts[kind]
    result["tasks"] = sum(task_counts.values())
    return result


def read_plan(path: str) -> tuple[dict[str, str], list[dict[str, object]]]:
    metadata: dict[str, str] = {}
    rows: list[dict[str, object]] = []
    columns: list[str] | None = None
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.rstrip("\n")
            if not line:
                continue
            if line.startswith("##"):
                key, separator, value = line[2:].partition("=")
                if not separator or not key:
                    raise ValueError(f"{path}:{line_number}: invalid metadata")
                metadata[key] = value
                continue
            if line.startswith("#"):
                columns = line[1:].split("\t")
                if tuple(columns) != PLAN_COLUMNS:
                    raise ValueError(f"{path}:{line_number}: unexpected columns")
                continue
            if columns is None:
                raise ValueError(f"{path}:{line_number}: missing plan header")
            values = line.split("\t")
            if len(values) != len(columns):
                raise ValueError(f"{path}:{line_number}: malformed plan row")
            row: dict[str, object] = dict(zip(columns, values))
            regions = json.loads(str(row["regions"]))
            if not isinstance(regions, list) or not regions:
                raise ValueError(f"{path}:{line_number}: empty regions")
            parsed_regions = []
            for region in regions:
                if (
                    not isinstance(region, list)
                    or len(region) != 4
                    or not isinstance(region[0], str)
                    or not isinstance(region[1], str)
                ):
                    raise ValueError(f"{path}:{line_number}: invalid region")
                start, end = int(region[2]), int(region[3])
                if start < 0 or end <= start:
                    raise ValueError(f"{path}:{line_number}: invalid region")
                parsed_regions.append((region[0], region[1], start, end))
            row["regions"] = parsed_regions
            row["estimated_records"] = int(str(row["estimated_records"]))
            rows.append(row)
    if metadata.get("format_version") != "2":
        raise ValueError(f"{path}: unsupported or missing format_version")
    if not rows:
        raise ValueError(f"{path}: plan contains no tasks")
    return metadata, rows


def vcf_header(
    reference: pysam.FastaFile,
    metadata: dict[str, str],
    row: dict[str, object],
) -> pysam.VariantHeader:
    header = pysam.VariantHeader()
    header.add_meta("fileformat", value="VCFv4.2")
    header.add_meta("source", value="spliceai-batched-universe")
    header.add_meta("reference", value=metadata["reference"])
    header.add_meta(
        "spliceai_batched_universe_kind",
        value=str(row["kind"]),
    )
    header.add_meta(
        "spliceai_batched_universe_definition",
        value=UNIVERSE_DEFINITIONS[str(row["kind"])],
    )
    header.add_meta(
        "spliceai_batched_reference_sha256",
        value=metadata["reference_sha256"],
    )
    header.add_meta(
        "spliceai_batched_annotation_release",
        value=metadata["annotation_release"],
    )
    header.add_meta(
        "spliceai_batched_annotation_sha256",
        value=metadata["annotation_sha256"],
    )
    reference_lengths = dict(zip(reference.references, reference.lengths))
    for annotation_contig, reference_contig, _, _ in row["regions"]:
        if annotation_contig not in header.contigs:
            header.contigs.add(
                annotation_contig,
                length=reference_lengths[reference_contig],
            )
    return header


def write_records(
    output: pysam.VariantFile,
    reference: pysam.FastaFile,
    kind: str,
    regions: list[tuple[str, str, int, int]],
    progress_every: int = 1_000_000,
    progress: TextIO = sys.stderr,
) -> int:
    records = 0
    next_progress = progress_every
    started = time.monotonic()
    for annotation_contig, reference_contig, start, end in regions:
        padding = 4 if kind == "indel" else 0
        sequence = reference.fetch(
            reference_contig,
            start,
            min(
                end + padding,
                reference.get_reference_length(reference_contig),
            ),
        ).upper()
        for offset in range(end - start):
            anchor = sequence[offset]
            if anchor not in DNA_BASES:
                continue
            position = start + offset
            if kind == "snv":
                for alternate in DNA_BASES:
                    if alternate == anchor:
                        continue
                    output.write(
                        output.new_record(
                            contig=annotation_contig,
                            start=position,
                            stop=position + 1,
                            alleles=(anchor, alternate),
                        )
                    )
                    records += 1
            else:
                for inserted in DNA_BASES:
                    output.write(
                        output.new_record(
                            contig=annotation_contig,
                            start=position,
                            stop=position + 1,
                            alleles=(anchor, anchor + inserted),
                        )
                    )
                    records += 1
                for deleted_bases in range(1, 5):
                    ref_end = offset + deleted_bases + 1
                    reference_allele = sequence[offset:ref_end]
                    if len(reference_allele) != deleted_bases + 1 or any(
                        base not in DNA_BASES for base in reference_allele
                    ):
                        continue
                    output.write(
                        output.new_record(
                            contig=annotation_contig,
                            start=position,
                            stop=position + len(reference_allele),
                            alleles=(reference_allele, anchor),
                        )
                    )
                    records += 1
            if progress_every and records >= next_progress:
                elapsed = time.monotonic() - started
                print(
                    f"generated={records} elapsed_seconds={elapsed:.1f} "
                    f"records_per_second={records / elapsed:.1f}",
                    file=progress,
                )
                next_progress += progress_every
    return records


def completion_is_valid(
    completion_path: Path,
    output_path: Path,
    plan_sha256: str,
    generator_sha256: str,
    threads: int,
) -> dict[str, object] | None:
    try:
        completion = json.loads(completion_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if (
        completion.get("plan_sha256") != plan_sha256
        or completion.get("generator_sha256") != generator_sha256
        or completion.get("compression_threads") != threads
        or not output_path.with_suffix(output_path.suffix + ".tbi").is_file()
        or completion.get("output_sha256") != sha256_file(str(output_path))
    ):
        return None
    return completion


def generate_task(
    plan_path: str,
    task_id: int,
    output_dir: str,
    reference_path: str | None = None,
    reference_sha256: str | None = None,
    threads: int = 1,
    progress_every: int = 1_000_000,
) -> dict[str, object]:
    metadata, rows = read_plan(plan_path)
    if task_id < 1 or task_id > len(rows):
        raise ValueError(f"--task-id must be between 1 and {len(rows)}")
    if threads < 1:
        raise ValueError("--threads must be positive")
    row = rows[task_id - 1]
    reference_value = reference_path or metadata["reference"]
    expected_reference_digest = metadata["reference_sha256"]
    if reference_sha256 is None:
        verified_sha256(
            reference_value,
            expected_reference_digest,
            "Reference",
        )
    elif reference_sha256.lower() != expected_reference_digest:
        raise ValueError(
            "Preverified reference checksum does not match the universe plan"
        )
    plan_digest = sha256_file(plan_path)
    generator_digest = sha256_file(__file__)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    shard_id = str(row["shard_id"])
    output_path = output_root / f"{shard_id}.vcf.gz"
    completion_path = output_root / f"{shard_id}.complete.json"
    if output_path.is_file():
        completion = completion_is_valid(
            completion_path,
            output_path,
            plan_digest,
            generator_digest,
            threads,
        )
        if completion is not None:
            return completion

    temporary = output_root / (f".{shard_id}.{os.getpid()}.partial.vcf.gz")
    temporary_index = Path(f"{temporary}.tbi")
    for stale in (temporary, temporary_index):
        if stale.exists():
            stale.unlink()

    completion_temporary = output_root / (f".{shard_id}.{os.getpid()}.complete.json")
    try:
        with pysam.FastaFile(reference_value) as reference:
            header = vcf_header(reference, metadata, row)
            with pysam.VariantFile(
                str(temporary),
                mode="wz",
                header=header,
                threads=threads,
            ) as output:
                record_count = write_records(
                    output,
                    reference,
                    str(row["kind"]),
                    list(row["regions"]),
                    progress_every=progress_every,
                )
        pysam.tabix_index(str(temporary), preset="vcf", force=True)
        output_sha256 = sha256_file(str(temporary))
        os.replace(temporary, output_path)
        os.replace(temporary_index, Path(f"{output_path}.tbi"))
        completion: dict[str, object] = {
            "format_version": 1,
            "shard_id": shard_id,
            "kind": row["kind"],
            "plan_sha256": plan_digest,
            "generator_sha256": generator_digest,
            "compression_threads": threads,
            "reference_sha256": expected_reference_digest,
            "annotation_sha256": metadata["annotation_sha256"],
            "records": record_count,
            "estimated_records": row["estimated_records"],
            "output": str(output_path.resolve()),
            "output_sha256": output_sha256,
        }
        with completion_temporary.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(completion, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(completion_temporary, completion_path)
        return completion
    finally:
        for stale in (temporary, temporary_index, completion_temporary):
            try:
                stale.unlink()
            except FileNotFoundError:
                pass


def write_scoring_manifest(
    plan_path: str,
    input_dir: str,
    output_path: str,
    verify_checksums: bool = False,
) -> dict[str, int]:
    metadata, rows = read_plan(plan_path)
    plan_digest = sha256_file(plan_path)
    generator_digest = sha256_file(__file__)
    input_root = Path(input_dir)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    counts = defaultdict(int)
    total_records = 0
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(output.parent),
            prefix=f".{output.name}.",
            suffix=".partial",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write("#shard_id\tinput_vcf\tinput_sha256\n")
            for row in rows:
                shard_id = str(row["shard_id"])
                completion_path = input_root / f"{shard_id}.complete.json"
                input_vcf = input_root / f"{shard_id}.vcf.gz"
                try:
                    completion = json.loads(completion_path.read_text(encoding="utf-8"))
                except (FileNotFoundError, json.JSONDecodeError) as exc:
                    raise ValueError(f"Incomplete universe shard {shard_id}") from exc
                if (
                    completion.get("shard_id") != shard_id
                    or completion.get("kind") != row["kind"]
                    or completion.get("plan_sha256") != plan_digest
                    or completion.get("generator_sha256") != generator_digest
                    or completion.get("reference_sha256")
                    != metadata["reference_sha256"]
                    or completion.get("annotation_sha256")
                    != metadata["annotation_sha256"]
                    or not input_vcf.is_file()
                    or not Path(f"{input_vcf}.tbi").is_file()
                ):
                    raise ValueError(f"Inconsistent universe shard {shard_id}")
                digest = str(completion.get("output_sha256", ""))
                if len(digest) != 64:
                    raise ValueError(f"Missing checksum for universe shard {shard_id}")
                if verify_checksums and sha256_file(str(input_vcf)) != digest:
                    raise ValueError(f"Checksum mismatch for universe shard {shard_id}")
                handle.write(f"{shard_id}\t{input_vcf.resolve()}\t{digest}\n")
                kind = str(row["kind"])
                records = int(completion["records"])
                counts[f"{kind}_shards"] += 1
                counts[f"{kind}_records"] += records
                total_records += records
            handle.flush()
            os.fsync(handle.fileno())
        assert temporary_path is not None
        os.replace(temporary_path, output)
    except BaseException:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
        raise
    counts["shards"] = len(rows)
    counts["records"] = total_records
    return dict(counts)


def print_summary(summary: dict[str, object]) -> None:
    print(" ".join(f"{key}={value}" for key, value in summary.items()))


def parse_kinds(value: str) -> tuple[str, ...]:
    if value == "both":
        return ("snv", "indel")
    return (value,)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create clean SNV/indel VCF shards from MANE and GRCh38",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--annotation", required=True)
    plan_parser.add_argument("--reference", required=True)
    plan_parser.add_argument("--output", required=True)
    plan_parser.add_argument("--target-records", type=int, default=1_000_000)
    plan_parser.add_argument(
        "--kind",
        choices=("snv", "indel", "both"),
        default="both",
    )
    plan_parser.add_argument("--annotation-release", default="unknown")
    plan_parser.add_argument("--annotation-sha256")
    plan_parser.add_argument("--reference-sha256")

    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("--plan", required=True)
    generate_parser.add_argument("--task-id", type=int, required=True)
    generate_parser.add_argument("--output-dir", required=True)
    generate_parser.add_argument("--reference")
    generate_parser.add_argument("--reference-sha256")
    generate_parser.add_argument("--threads", type=int, default=1)
    generate_parser.add_argument("--progress-every", type=int, default=1_000_000)

    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--plan", required=True)
    finalize_parser.add_argument("--input-dir", required=True)
    finalize_parser.add_argument("--output", required=True)
    finalize_parser.add_argument("--verify-checksums", action="store_true")

    args = parser.parse_args()
    if args.command == "plan":
        print_summary(
            write_plan(
                args.annotation,
                args.reference,
                args.output,
                target_records=args.target_records,
                kinds=parse_kinds(args.kind),
                annotation_release=args.annotation_release,
                annotation_sha256=args.annotation_sha256,
                reference_sha256=args.reference_sha256,
            )
        )
    elif args.command == "generate":
        print_summary(
            generate_task(
                args.plan,
                args.task_id,
                args.output_dir,
                reference_path=args.reference,
                reference_sha256=args.reference_sha256,
                threads=args.threads,
                progress_every=args.progress_every,
            )
        )
    else:
        print_summary(
            write_scoring_manifest(
                args.plan,
                args.input_dir,
                args.output,
                verify_checksums=args.verify_checksums,
            )
        )


if __name__ == "__main__":
    main()
