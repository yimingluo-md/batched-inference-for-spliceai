# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare SpliceAI VCF annotations while ignoring header text."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


def records(path: str) -> list[tuple[tuple[str, ...], str]]:
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 8:
                raise ValueError(
                    f"{path}:{line_number}: expected at least 8 "
                    f"tab-separated VCF columns, found {len(fields)}"
                )
            info = fields[7]
            spliceai = next(
                (
                    item.split("=", 1)[1]
                    for item in info.split(";")
                    if item.startswith("SpliceAI=")
                ),
                "",
            )
            rows.append((tuple(fields[:5]), spliceai))
    return rows


@dataclass
class Comparison:
    candidate: str
    records: int
    identity_different: int = 0
    annotations_different: int = 0
    annotation_entries_missing: int = 0
    score_fields_different: int = 0
    max_score_difference: float = 0.0
    position_fields_different: int = 0
    nontrivial_position_fields_different: int = 0


def annotation_map(value: str) -> dict[tuple[str, str], list[str]]:
    result = {}
    if not value:
        return result
    for item in value.split(","):
        parts = item.split("|")
        if len(parts) == 10:
            result[(parts[0], parts[1])] = parts
    return result


def compare(
    baseline_path: str,
    candidate_path: str,
    details_path: str | None = None,
) -> Comparison:
    baseline = records(baseline_path)
    candidate = records(candidate_path)
    result = Comparison(candidate=candidate_path, records=len(candidate))
    if len(candidate) != len(baseline):
        result.identity_different = abs(len(candidate) - len(baseline))
        return result

    details = []
    for (left_id, left_info), (right_id, right_info) in zip(baseline, candidate):
        if left_id != right_id:
            result.identity_different += 1
        if left_info == right_info:
            continue
        details.append((*left_id, left_info, right_info))
        result.annotations_different += 1
        left_entries = annotation_map(left_info)
        right_entries = annotation_map(right_info)
        result.annotation_entries_missing += len(
            set(left_entries).symmetric_difference(right_entries)
        )
        for key in set(left_entries) & set(right_entries):
            left_parts = left_entries[key]
            right_parts = right_entries[key]
            for index in range(2, 6):
                if left_parts[index] != right_parts[index]:
                    result.score_fields_different += 1
                    if left_parts[index] != "." and right_parts[index] != ".":
                        result.max_score_difference = max(
                            result.max_score_difference,
                            abs(float(left_parts[index]) - float(right_parts[index])),
                        )
            for index in range(6, 10):
                if left_parts[index] != right_parts[index]:
                    result.position_fields_different += 1
                    score_index = index - 4
                    scores = (left_parts[score_index], right_parts[score_index])
                    if (
                        all(value != "." for value in scores)
                        and max(float(value) for value in scores) > 0.01
                    ):
                        result.nontrivial_position_fields_different += 1
    if details_path:
        with open(details_path, "w", encoding="utf-8") as handle:
            handle.write(
                "CHROM\tPOS\tID\tREF\tALT\tBASELINE_SPLICEAI\tCANDIDATE_SPLICEAI\n"
            )
            handle.writelines("\t".join(row) + "\n" for row in details)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline")
    parser.add_argument("comparisons", nargs="+")
    parser.add_argument("--json", dest="json_path")
    parser.add_argument("--details-dir")
    parser.add_argument("--max-score-difference", type=float, default=0.011)
    args = parser.parse_args()

    if args.details_dir:
        Path(args.details_dir).mkdir(parents=True, exist_ok=True)
    results = []
    for path in args.comparisons:
        details_path = None
        if args.details_dir:
            details_path = str(
                Path(args.details_dir) / f"{Path(path).name}.differences.tsv"
            )
        results.append(compare(args.baseline, path, details_path))
    failed = False
    for result in results:
        print(
            f"{result.candidate}: records={result.records} "
            f"identity_different={result.identity_different} "
            f"annotations_different={result.annotations_different} "
            f"annotation_entries_missing={result.annotation_entries_missing} "
            f"score_fields_different={result.score_fields_different} "
            f"max_score_difference={result.max_score_difference:.3f} "
            f"position_fields_different={result.position_fields_different} "
            "nontrivial_position_fields_different="
            f"{result.nontrivial_position_fields_different}"
        )
        failed |= bool(
            result.identity_different
            or result.annotation_entries_missing
            or result.max_score_difference > args.max_score_difference
            or result.nontrivial_position_fields_different
        )
    if args.json_path:
        Path(args.json_path).write_text(
            json.dumps([asdict(result) for result in results], indent=2) + "\n",
            encoding="utf-8",
        )
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
