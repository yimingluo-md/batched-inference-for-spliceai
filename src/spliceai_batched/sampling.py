# SPDX-License-Identifier: GPL-3.0-or-later
"""Create a deterministic, transcript-stratified VCF sample from indexed resources."""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import pysam

PRIMARY_CONTIGS = [str(value) for value in range(1, 23)] + ["X", "Y"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--annotation", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--target-records", type=int, default=25_000)
    parser.add_argument("--genes-per-stratum", type=int, default=12)
    parser.add_argument("--window", type=int, default=750)
    return parser.parse_args()


def read_annotations(path: str) -> dict[tuple[str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    with open(path, encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            chrom = row["CHROM"]
            strand = row["STRAND"]
            if chrom in PRIMARY_CONTIGS and strand in {"+", "-"}:
                grouped[(chrom, strand)].append(row)
    for rows in grouped.values():
        rows.sort(key=lambda item: (int(item["TX_START"]), item["#NAME"]))
    return grouped


def quantile_rows(rows: list[dict[str, str]], count: int) -> list[dict[str, str]]:
    if count < 1:
        raise ValueError("count must be at least 1")
    if len(rows) <= count:
        return rows
    return [rows[index] for index in evenly_spaced_indexes(len(rows), count)]


def evenly_spaced_indexes(length: int, count: int) -> list[int]:
    """Return deterministic indexes spanning a sequence, including count=1."""
    if count < 1:
        raise ValueError("count must be at least 1")
    if length < 1:
        return []
    if count >= length:
        return list(range(length))
    if count == 1:
        return [(length - 1) // 2]
    return sorted({round(index * (length - 1) / (count - 1)) for index in range(count)})


def anchors(row: dict[str, str]) -> list[int]:
    exon_starts = [
        int(value) for value in row["EXON_START"].rstrip(",").split(",") if value
    ]
    exon_ends = [
        int(value) for value in row["EXON_END"].rstrip(",").split(",") if value
    ]
    candidates = [int(row["TX_START"]), int(row["TX_END"])]
    boundaries = sorted(set(exon_starts[1:] + exon_ends[:-1]))
    if boundaries:
        candidates.extend(
            boundaries[index]
            for index in sorted(
                {
                    0,
                    len(boundaries) // 2,
                    len(boundaries) - 1,
                }
            )
        )
    return sorted(set(candidates))


def strip_spliceai(record_text: str) -> str:
    fields = record_text.rstrip("\n").split("\t")
    info = [
        value
        for value in fields[7].split(";")
        if value and not value.startswith("SpliceAI=")
    ]
    fields[7] = ";".join(info) if info else "."
    return "\t".join(fields) + "\n"


def main() -> None:
    args = parse_args()
    if args.target_records < 1:
        raise SystemExit("--target-records must be at least 1")
    if args.genes_per_stratum < 1:
        raise SystemExit("--genes-per-stratum must be at least 1")
    annotations = read_annotations(args.annotation)
    selected = []
    for chrom in PRIMARY_CONTIGS:
        for strand in ("+", "-"):
            selected.extend(
                quantile_rows(
                    annotations.get((chrom, strand), []),
                    args.genes_per_stratum,
                )
            )
    if not selected:
        raise SystemExit("No annotations selected")

    quota = max(1, math.ceil(args.target_records / len(selected)))
    source = pysam.VariantFile(args.input)
    contig_order = {name: index for index, name in enumerate(source.header.contigs)}
    records: dict[tuple[str, int, str, str], str] = {}
    gene_counts: dict[str, int] = defaultdict(int)

    for row in selected:
        chrom = row["CHROM"]
        gene = row["#NAME"]
        for anchor in anchors(row):
            start = max(0, anchor - args.window)
            stop = anchor + args.window + 1
            for record in source.fetch(chrom, start, stop):
                key = (
                    record.chrom,
                    record.pos,
                    record.ref,
                    ",".join(record.alts or ()),
                )
                if key in records:
                    continue
                records[key] = strip_spliceai(str(record))
                gene_counts[gene] += 1
                if gene_counts[gene] >= quota:
                    break
            if gene_counts[gene] >= quota:
                break

    ordered = sorted(
        records.items(),
        key=lambda item: (
            contig_order[item[0][0]],
            item[0][1],
            item[0][2],
            item[0][3],
        ),
    )
    if len(ordered) > args.target_records:
        # Evenly retain records so later chromosomes are not truncated.
        ordered = [
            ordered[index]
            for index in evenly_spaced_indexes(
                len(ordered),
                args.target_records,
            )
        ]

    header_lines = [
        line
        for line in str(source.header).splitlines(keepends=True)
        if not line.startswith("##INFO=<ID=SpliceAI,")
    ]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        handle.writelines(header_lines)
        handle.writelines(text for _, text in ordered)

    observed_contigs = len({key[0] for key, _ in ordered})
    print(
        f"records={len(ordered)} selected_genes={len(selected)} "
        f"represented_contigs={observed_contigs} output={output}"
    )


if __name__ == "__main__":
    main()
