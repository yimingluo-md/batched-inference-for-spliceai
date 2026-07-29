# SPDX-License-Identifier: GPL-3.0-or-later
"""Convert an NCBI MANE Ensembl GTF to SpliceAI's annotation table format."""

from __future__ import annotations

import argparse
import gzip
import re
from collections import defaultdict
from pathlib import Path
from typing import TextIO

ATTRIBUTE = re.compile(r"(\S+)\s+\"([^\"]*)\"")
PRIMARY_CONTIGS = {str(value) for value in range(1, 23)} | {"X", "Y"}


def attributes(text: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for key, value in ATTRIBUTE.findall(text):
        result[key].append(value)
    return dict(result)


def open_text(path: str) -> TextIO:
    if path.endswith(".gz"):
        return gzip.open(path, mode="rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def convert(
    input_path: str,
    output_path: str,
    include_nonprimary: bool = False,
) -> dict[str, int]:
    transcripts: dict[str, dict[str, object]] = {}
    exons: dict[str, list[tuple[int, int]]] = defaultdict(list)

    with open_text(input_path) as handle:
        for line in handle:
            if not line or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9 or fields[2] not in {"transcript", "exon"}:
                continue
            attrs = attributes(fields[8])
            transcript_id = attrs.get("transcript_id", [None])[0]
            if not transcript_id:
                continue
            if fields[2] == "transcript":
                if "MANE_Select" not in attrs.get("tag", []):
                    continue
                chrom = fields[0][3:] if fields[0].startswith("chr") else fields[0]
                if not include_nonprimary and chrom not in PRIMARY_CONTIGS:
                    continue
                gene_name = attrs.get("gene_name", [None])[0]
                if not gene_name:
                    raise ValueError(f"Missing gene_name for {transcript_id}")
                transcripts[transcript_id] = {
                    "name": gene_name,
                    "chrom": chrom,
                    "strand": fields[6],
                    "start": int(fields[3]) - 1,
                    "end": int(fields[4]),
                }
            else:
                exons[transcript_id].append((int(fields[3]) - 1, int(fields[4])))

    rows = []
    for transcript_id, transcript in transcripts.items():
        transcript_exons = sorted(set(exons.get(transcript_id, [])))
        if not transcript_exons:
            raise ValueError(f"No exons for MANE Select transcript {transcript_id}")
        if transcript_exons[0][0] < int(transcript["start"]):
            raise ValueError(f"Exon precedes transcript start for {transcript_id}")
        if transcript_exons[-1][1] > int(transcript["end"]):
            raise ValueError(f"Exon exceeds transcript end for {transcript_id}")
        rows.append(
            (
                str(transcript["chrom"]),
                int(transcript["start"]),
                str(transcript["name"]),
                str(transcript["strand"]),
                int(transcript["end"]),
                transcript_exons,
            )
        )

    contig_order = {str(index): index for index in range(1, 23)}
    contig_order.update({"X": 23, "Y": 24, "M": 25, "MT": 25})
    rows.sort(
        key=lambda row: (
            contig_order.get(row[0], 10_000),
            row[0],
            row[1],
            row[2],
        )
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        handle.write("#NAME\tCHROM\tSTRAND\tTX_START\tTX_END\tEXON_START\tEXON_END\n")
        for chrom, start, name, strand, end, transcript_exons in rows:
            exon_starts = ",".join(str(value[0]) for value in transcript_exons) + ","
            exon_ends = ",".join(str(value[1]) for value in transcript_exons) + ","
            handle.write(
                f"{name}\t{chrom}\t{strand}\t{start}\t{end}\t"
                f"{exon_starts}\t{exon_ends}\n"
            )

    return {
        "transcripts": len(rows),
        "genes": len({row[2] for row in rows}),
        "contigs": len({row[0] for row in rows}),
        "exons": sum(len(row[5]) for row in rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--include-nonprimary",
        action="store_true",
        help="Retain MANE transcripts on GRCh38 patch and alternate contigs",
    )
    args = parser.parse_args()
    summary = convert(
        args.input,
        args.output,
        include_nonprimary=args.include_nonprimary,
    )
    print(" ".join(f"{key}={value}" for key, value in summary.items()))


if __name__ == "__main__":
    main()
